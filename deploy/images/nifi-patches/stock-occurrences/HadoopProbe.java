import java.util.Arrays;
import org.apache.hadoop.io.compress.snappy.SnappyCompressor;
import org.xerial.snappy.Snappy;

/** A normal highly compressible input, never hostile old native input. */
public class HadoopProbe {
  public static void main(String[] args) throws Exception {
    byte[] data = new byte[4096]; Arrays.fill(data, (byte)'A');
    var consumer = new SnappyCompressor(4096);
    consumer.setInput(data, 0, data.length); consumer.finish();
    byte[] out = new byte[8192];
    try {
      int n = consumer.compress(out, 0, out.length);
      if (!Arrays.equals(data, Snappy.uncompress(Arrays.copyOf(out, n)))) throw new AssertionError("roundtrip");
      if (!args[0].equals("old")) throw new AssertionError("expected stricter precondition rejection");
      System.out.println("old Hadoop normal 4096-byte roundtrip PASS");
    } catch (IllegalArgumentException e) {
      if (!args[0].equals("new") || e.getMessage() == null ||
          !e.getMessage().contains("not enough space for output") ||
          !e.getMessage().contains("remaining")) throw e;
      System.out.println("CONFIRMED new Snappy rejects Hadoop normal compression: " + e);
    }
  }
}
