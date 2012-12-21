
package water.api;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import water.*;

public class Cloud extends Request {

  public Cloud() {
    _requestHelp = "Displays the information about the current cloud. For each"
            + " node displays its heartbeat information.";
  }

  @Override public Response serve() {
    JsonObject response = new JsonObject();
    final H2O cloud = H2O.CLOUD;
    final H2ONode self = H2O.SELF;
    response.addProperty(JSON_CLOUD_NAME, H2O.NAME);
    response.addProperty(JSON_NODE_NAME, self.toString());
    response.addProperty(JSON_CLOUD_SIZE, cloud._memary.length);
    JsonArray nodes = new JsonArray();
    for (H2ONode h2o : cloud._memary) {
      HeartBeat hb = h2o._heartbeat;
      JsonObject node = new JsonObject();
      node.addProperty(JSON_NODES_NAME,h2o.toString());
      node.addProperty(JSON_NODES_NUM_KEYS, hb._keys);
      node.addProperty(JSON_NODES_VAL_SIZE, hb.get_valsz());
      node.addProperty(JSON_NODES_FREE_MEM, hb.get_free_mem());
      node.addProperty(JSON_NODES_TOT_MEM, hb.get_tot_mem());
      node.addProperty(JSON_NODES_MAX_MEM, hb.get_max_mem());
      node.addProperty(JSON_NODES_FREE_DISK, hb.get_free_disk());
      node.addProperty(JSON_NODES_MAX_DISK, hb.get_max_disk());
      node.addProperty(JSON_NODES_NUM_CPUS, (int)hb._num_cpus);
      node.addProperty(JSON_NODES_CPU_UTIL, hb.get_cpu_util());
      node.addProperty(JSON_NODES_CPU_LOAD_1, pos_neg(hb.get_cpu_load1()));
      node.addProperty(JSON_NODES_CPU_LOAD_5, pos_neg(hb.get_cpu_load5()));
      node.addProperty(JSON_NODES_CPU_LOAD_15, pos_neg(hb.get_cpu_load15()));
      node.addProperty(JSON_NODES_FJ_THREADS_HI, (int)hb._fjthrds_hi);
      node.addProperty(JSON_NODES_FJ_QUEUE_HI, (int)hb._fjqueue_hi);
      node.addProperty(JSON_NODES_FJ_THREADS_LO, (int)hb._fjthrds_lo);
      node.addProperty(JSON_NODES_FJ_QUEUE_LO, (int)hb._fjqueue_lo);
      node.addProperty(JSON_NODES_RPCS, (int)hb._rpcs);
      node.addProperty(JSON_NODES_TCPS_ACTIVE, (int) hb._tcps_active);
      nodes.add(node);
    }
    response.add(JSON_NODES,nodes);
    response.addProperty(JSON_CONSENSUS, Paxos._commonKnowledge); // Cloud is globally accepted
    response.addProperty(JSON_LOCKED, Paxos._cloudLocked); // Cloud is locked against changes
    Response r = Response.done(response);
    r.setBuilder(JSON_CONSENSUS, new BooleanStringBuilder("","Voting new members"));
    r.setBuilder(JSON_LOCKED, new BooleanStringBuilder("Locked","Accepting new members"));
    return r;
  }

  public static String pos_neg(double d) {
    return d >= 0 ? String.valueOf(d) : "n/a";
  }

}
