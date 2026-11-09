import java.nio.ByteBuffer;
import org.xerial.snappy.Snappy;

/** Snappy's upstream #766 contract: limit zero is valid, undersized allocation is not. */
public final class CompressionExercise {
    public static void main(String[] args) throws Exception {
        CompatibilityProbe.main(new String[] {"normal"});
        byte[] data = "bounded normal input".repeat(10).getBytes(java.nio.charset.StandardCharsets.UTF_8);
        ByteBuffer input = ByteBuffer.allocateDirect(data.length);
        input.put(data).flip();
        ByteBuffer output = ByteBuffer.allocateDirect(Snappy.maxCompressedLength(data.length) + 17);
        output.position(17).limit(17);
        int size = Snappy.compress(input, output);
        if (output.position() != 17 || output.limit() != 17 + size) {
            throw new AssertionError("official empty-limit/offset contract changed");
        }
        ByteBuffer decoded = ByteBuffer.allocateDirect(data.length);
        Snappy.uncompress(output, decoded);
        byte[] restored = new byte[data.length];
        decoded.get(restored);
        if (!java.util.Arrays.equals(data, restored)) throw new AssertionError("direct offset roundtrip");
        input.rewind();
        ByteBuffer parent = ByteBuffer.allocateDirect(4096);
        parent.position(40).limit(41);
        try {
            Snappy.compress(input, parent.slice());
            throw new AssertionError("undersized slice accepted before JNI");
        } catch (IllegalArgumentException expected) {
            if (!expected.getMessage().contains("not enough space for output")) throw expected;
        }
        System.out.println("PASS official Snappy empty-limit/offset semantics and undersized-slice negative");
    }
}
