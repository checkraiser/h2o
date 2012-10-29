package hex.rf;
import hex.rf.Tree.StatType;

import java.util.*;

import jsr166y.RecursiveAction;
import water.*;

/**
 * Distributed RandomForest
 * @author cliffc
 */
public class DRF extends water.DRemoteTask {
  // Cloud-wide data
  int _ntrees;          // Number of trees TOTAL, not per-node
  int _depth;           // Tree-depth limiter
  int _stat;            // Use Gini(1) or Entropy(0) for splits
  int _classcol;        // Column being classified
  Key _arykey;          // The ValueArray being RF'd
  Key _modelKey;        // Where to jam the final trees
  public Key _treeskey; // Key of Tree-Keys built so-far
  int[] _ignores;

  // Node-local data
  transient Data _validation;        // Data subset to validate with locally, or NULL
  transient RandomForest _rf;        // The local RandomForest
  transient int _seed;

  public static class IllegalDataException extends Error {
    public IllegalDataException(String string) {
      super(string);
    }
  }

  private void validateInputData(ValueArray ary){
    final int classes = (int)(ary.col_max(_classcol) - ary.col_min(_classcol))+1;
    // There is no point in running Rf when all the training data have the same class
    if( !(2 <= classes && classes <= 65534 ) )
      throw new IllegalDataException("Number of classes must be >= 2 and <= 65534, found " + classes);
  }

  public static DRF web_main( ValueArray ary, int ntrees, int depth, double cutRate, StatType stat, int seed, int classcol, int[] ignores, Key modelKey) {
    // Make a Task Key - a Key used by all nodes to report progress on RF
    DRF drf = new DRF();
    drf._ntrees = ntrees;
    drf._depth = depth;
    drf._stat = stat.ordinal();
    drf._arykey = ary._key;
    drf._classcol = classcol;
    drf._treeskey = Key.make("Trees of "+ary._key,(byte)1,Key.KEY_OF_KEYS);
    drf._seed = seed;
    drf._ignores = ignores;
    drf._modelKey = modelKey;
    drf.validateInputData(ary);
    DKV.put(drf._treeskey, new Value(drf._treeskey, 4)); //4 bytes for the key-count, which is zero
    DKV.write_barrier();
    drf.fork(ary._key);
    return drf;
  }

  public final  DataAdapter extractData(Key arykey, Key [] keys){
    final ValueArray ary = (ValueArray)DKV.get(arykey);
    final int rowsize = ary.row_size();

    // One pass over all chunks to compute max rows

    int num_rows = 0;
    int unique = -1;
    for( Key key : keys )
      if( key.home() ) {
        num_rows += DKV.get(key)._max/rowsize;
        if( unique == -1 )
          unique = ValueArray.getChunkIndex(key);
      }
    // The data adapter...
    final DataAdapter dapt = new DataAdapter(ary, _classcol, _ignores, num_rows, unique, _seed);
    // Now load the DataAdapter with all the rows on this Node
    int ncolumns = ary.num_cols();

    ArrayList<RecursiveAction> binningJobs = new ArrayList<RecursiveAction>();
    ArrayList<RecursiveAction> simpleJobs = new ArrayList<RecursiveAction>();

    final Key [] ks = keys;

    for(int i = 0; i < ncolumns; ++i){
      final int col = i;
      if(dapt.binColumn(col)){
        binningJobs.add(new RecursiveAction() {
          @Override
          protected void compute() {
            int start_row = 0;
            for(Key k:ks){
              if(!k.home())continue;
              byte[] bits = DKV.get(k).get();
              final int rows = bits.length/rowsize;
              for( int j = 0; j < rows; j++ ) { // For all rows in this chunk
                if( !ary.valid(bits,j,rowsize,col)) continue;
                dapt.addValueRaw((float)ary.datad(bits,j,rowsize,col), j + start_row, col);
              }
              start_row += rows;
            }
            dapt.shrinkColumn(col);
          }
        });
      }
    }
    int rpc = (int)(ValueArray.chunk_size() / ary.row_size());
    int start_row = 0;
    for(final Key k:ks) {
      final int S = start_row;
      if(!k.home())continue;
      simpleJobs.add(new RecursiveAction() {
        @Override
        protected void compute() {
          byte[] bits = DKV.get(k).get();
          final int rows = bits.length/rowsize;
          ROWS:for(int j = 0; j < rows; ++j){
            for(int c = 0; c < ary.num_cols(); ++c){
              if( !ary.valid(bits,j,rowsize,c)) continue ROWS;
              if(dapt.binColumn(c))
                dapt.addValue((float)ary.datad(bits,j,rowsize,c), j + S, c);
              else{
                long v = ary.data(bits,j,rowsize,c);
                v -= ary.col_min(c);
                dapt.addValue((short)v, S+j, c);
              }
            }
          }
        }
      });
      start_row += rpc;
    }
    invokeAll(binningJobs);
    invokeAll(simpleJobs);
    return dapt;
  }
  // Local RF computation.
  public final void compute() {
    DataAdapter dapt = extractData(_arykey, _keys);
    Utils.pln("[RF] Data adapter built");
    // If we have too little data to validate distributed, then
    // split the data now with sampling and train on one set & validate on the other.
    sample = (!forceNoSample) && sample || _keys.length < 2; // Sample if we only have 1 key, hence no distribution
    Data d = Data.make(dapt);
    short[] complement = sample ? new short[d.rows()] : null;
    Data t = sample ? d.sampleWithReplacement(.666, complement) : d;
    _validation = sample ? t.complement(d, complement) : null;

    // Figure the number of trees to make locally, so the total hits ntrees.
    // Divide equally amongst all the nodes that actually have data.
    // First: compute how many nodes have data.
    ValueArray ary = (ValueArray)DKV.get(_arykey);
    final long num_chunks = ary.chunks();
    final int num_nodes = H2O.CLOUD.size();
    HashSet<H2ONode> nodes = new HashSet();
    for( long i=0; i<num_chunks; i++ ) {
      nodes.add(ary.chunk_get(i).home_node());
      if( nodes.size() == num_nodes ) // All of them?
        break;                        // Done
    }

    H2ONode[] array = nodes.toArray(new H2ONode[nodes.size()]);
    Arrays.sort(array);
    // Give each Node ntrees/#nodes worth of trees.  Round down for later nodes,
    // and round up for earlier nodes.
    int ntrees = _ntrees/nodes.size();
    if( Arrays.binarySearch(array, H2O.SELF) < _ntrees - ntrees*nodes.size() )
      ++ntrees;

    // Make a single RandomForest to that does all the tree-construction work.
    Utils.pln("[RF] Building "+ntrees+" trees");
    _rf = new RandomForest(this, t, ntrees, _depth, 0.0, StatType.values()[_stat]);
    tryComplete();
  }

  static boolean sample;
  static boolean forceNoSample = false;

  public void reduce( DRemoteTask drt ) { }
}
