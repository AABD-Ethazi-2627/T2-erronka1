import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.StringJoiner;
import shaded.parquet.com.fasterxml.jackson.annotation.JsonCreator;
import shaded.parquet.com.fasterxml.jackson.annotation.JsonIdentityInfo;
import shaded.parquet.com.fasterxml.jackson.annotation.JsonValue;
import shaded.parquet.com.fasterxml.jackson.annotation.ObjectIdGenerators;
import shaded.parquet.com.fasterxml.jackson.core.type.TypeReference;
import shaded.parquet.com.fasterxml.jackson.databind.ObjectMapper;
import shaded.parquet.com.fasterxml.jackson.databind.json.JsonMapper;

/** Benign deterministic reference-order control; no timing, native codec or services. */
public final class ParquetJacksonReferenceProbe {
    private static long equalsCalls;

    public static final class Key {
        final int value;
        @JsonCreator(mode = JsonCreator.Mode.DELEGATING)
        public Key(int value) { this.value = value; }
        @JsonValue public int value() { return value; }
        @Override public int hashCode() { return value; }
        @Override public boolean equals(Object other) {
            equalsCalls++;
            return other instanceof Key key && key.value == value;
        }
    }

    @JsonIdentityInfo(generator = ObjectIdGenerators.PropertyGenerator.class, property = "id")
    public static final class Node { public Key id; }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        Path origin = Path.of(ObjectMapper.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
        require(origin.equals(Path.of(args[1]).toRealPath()), "mapper origin drift");
        ObjectMapper mapper = JsonMapper.builder().build();
        int count = 128;
        StringJoiner json = new StringJoiner(",", "[", "]");
        for (int i = 1; i <= count; i++) json.add(Integer.toString(i));
        for (int i = count; i >= 1; i--) json.add("{\"id\":" + i + "}");
        equalsCalls = 0;
        List<Node> reversed = mapper.readValue(json.toString(), new TypeReference<List<Node>>() {});
        long observed = equalsCalls;
        require(reversed.size() == count * 2, "reference count");
        for (int i = 0; i < count; i++) {
            require(reversed.get(i) == reversed.get(2 * count - 1 - i), "reverse identity");
            require(reversed.get(i).id.value == i + 1, "reference ordering");
        }
        require(observed == Long.parseLong(args[0]), "unexpected Key.equals count: " + observed);
        List<Node> interleaved = mapper.readValue(
            "[1,{\"id\":100},2,{\"id\":101},{\"id\":2},{\"id\":1}]",
            new TypeReference<List<Node>>() {});
        require(interleaved.get(0) == interleaved.get(5), "interleaved list identity 1");
        require(interleaved.get(2) == interleaved.get(4), "interleaved list identity 2");
        LinkedHashMap<String, Node> map = mapper.readValue(
            "{\"a\":1,\"b\":{\"id\":2},\"c\":3,\"d\":{\"id\":3},\"e\":{\"id\":1}}",
            new TypeReference<LinkedHashMap<String, Node>>() {});
        require(map.get("a") == map.get("e") && map.get("c") == map.get("d"), "map reference identity");
        require(String.join(",", map.keySet()).equals("a,b,c,d,e"), "map insertion order");
        System.out.println("reference-count=" + count + " Key.equals=" + observed
            + " reverse/interleaved/map identity-and-order=passed mapper=" + origin);
    }
}
