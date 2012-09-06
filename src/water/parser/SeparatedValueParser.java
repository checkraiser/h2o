package water.parser;

import java.util.Iterator;

import water.*;

import com.google.common.base.Objects;

public class SeparatedValueParser implements Iterable<double[]>, Iterator<double[]> {
  private final Key _key;
  private final Value _startVal;
  private final char _separator;

  private Value _curVal;
  private int _curChunk;
  private byte[] _curData;
  private int _offset;

  private final DecimalParser _decimal = new DecimalParser();
  private final double[] _fieldVals;

  public SeparatedValueParser(Key k, char seperator, int numColumnsGuess) {
    _separator = seperator;
    _startVal = UKV.get(k);
    assert _startVal != null;
    _key = _startVal._key;

    if( _key._kb[0] == Key.ARRAYLET_CHUNK ) {
      _curChunk = ValueArray.getChunkIndex(_key);
    } else {
      _curChunk = -1;
    }

    _curVal = _startVal;
    _offset = 0;
    _curData = _startVal.get();
    if( _curChunk > 0 ) {
      while( hasNextByte() ) {
        byte b = getByte();
        if( isNewline(b) ) break;
        ++_offset;
      }
    }
    skipNewlines();

    _fieldVals = new double[numColumnsGuess];
  }

  // we are splitting this method, to clue in hotspot that the fast path
  // should be inlined
  private boolean hasNextByte() {
    if( _offset < _curData.length ) return true;
    return hasNextByteInSeparateChunk();
  }
  private boolean hasNextByteInSeparateChunk() {
    if( _curChunk < 0 ) return false;

    if( _offset < _curVal._max ) {
      _curData = _curVal.get(2*_curData.length);
      return true;
    }

    _curChunk += 1;
    Key k = ValueArray.getChunk(_key, _curChunk);
    _curVal = UKV.get(k);
    if (_curVal == null) return false;
    _offset = 0;
    _curData = _curVal.get(1024);
    return _offset < _curData.length;
  }

  private byte getByte() {
    assert hasNextByte();
    return _curData[_offset];
  }

  private void skipNewlines() {
    while( hasNextByte() ) {
      byte b = getByte();
      if( !isNewline(b) ) return;
      ++_offset;
    }
  }

  // According to the CSV spec, `"asdf""asdf"` is a legal quoted field
  // We are going to parse this, but not simplify it into `asdf"asdf`
  // we will make the simplifying parse of " starts and stops escaping
  private byte scanPastNextSeparator() {
    boolean escaped = false;
    while( hasNextByte() ) {
      byte b = getByte();
      if( b == '"' ) {
        escaped = !escaped;
      } else if( !escaped && isSeparator(b) ) {
        ++_offset;
        return b;
      }
      _decimal.addCharacter(b);
      ++_offset;
    }
    return '\n';
  }

  private boolean isNewline(byte b)  { return b == '\r' || b == '\n'; }
  private boolean isSeparator(byte b) { return b == _separator || isNewline(b); }

  @Override
  public Iterator<double[]> iterator() {
    return this;
  }

  @Override
  public boolean hasNext() {
    return _curVal == _startVal && hasNextByte();
  }

  @Override
  public double[] next() {
    assert !isNewline(getByte());

    byte b;
    int field = 0;
    while( hasNextByte() ) {
      if( field < _fieldVals.length ) {
        _decimal.reset();
        b = scanPastNextSeparator();
        _fieldVals[field] = _decimal.doubleValue();
      } else {
        b = scanPastNextSeparator();
      }
      ++field;
      if( isNewline(b) ) {
        break;
      }
    }
    for(; field < _fieldVals.length; ++field) _fieldVals[field] = Double.NaN;
    skipNewlines();
    return _fieldVals;
  }

  public String toString() {
    return Objects.toStringHelper(this)
        .add("curChunk", _curChunk)
        .add("_offset", _offset) + "\n" +
        new String(_curData, _offset, Math.min(100, _curData.length - _offset));
  }


  @Override public void remove() { throw new UnsupportedOperationException(); }
}
