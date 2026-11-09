import com.hazelcast.jet.json.JsonUtil;
import com.hazelcast.core.HazelcastJsonValue;
import com.hazelcast.internal.serialization.impl.DefaultSerializationServiceBuilder;
import java.util.*;
public class HazelcastProbe {
  public static void main(String[] args) throws Exception {
    Map<String,Object> m = JsonUtil.mapFrom("{\"a\":[1,2],\"label\":\"é\",\"n\":null}");
    if (!m.containsKey("n") || m.get("n")!=null) throw new AssertionError("null parsing");
    Map<String,Object> expected = new HashMap<>(m); expected.remove("n");
    // jackson-jr's default serializer omits null map values in stock Hazelcast.
    if (!expected.equals(JsonUtil.mapFrom(JsonUtil.toJson(m)))) throw new AssertionError("Hazelcast/Jackson jr map path");
    var s = new DefaultSerializationServiceBuilder().build();
    try {
      HazelcastJsonValue v = new HazelcastJsonValue("{\"label\":\"é\",\"n\":null}");
      Object restored = s.toObject(s.toData(v));
      if (!v.equals(restored)) throw new AssertionError("Hazelcast JSON serialization");
    } finally { s.dispose(); }
    System.out.println("Hazelcast JSON/Jackson jr + standalone serialization=pass source="
      +JsonUtil.class.getProtectionDomain().getCodeSource().getLocation());
  }
}
