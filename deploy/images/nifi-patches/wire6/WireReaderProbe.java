import com.squareup.wire.ByteArrayProtoReader32;
import com.squareup.wire.ProtoReader;
import java.io.IOException;
import java.util.HexFormat;
import okio.Buffer;

/** Real upstream readers: positive input and both published advisory boundaries. */
public final class WireReaderProbe {
    private static int failures;

    private static void check(boolean fast, String name, String hex, boolean valid) {
        try {
            byte[] bytes = HexFormat.of().parseHex(hex);
            if (fast) {
                ByteArrayProtoReader32 reader = new ByteArrayProtoReader32(bytes, 0, bytes.length);
                reader.beginMessage();
                int tag = reader.nextTag();
                if (valid) {
                    if (tag != 1 || reader.readVarint32() != 150 || reader.nextTag() != -1) {
                        throw new AssertionError("valid scalar changed");
                    }
                } else if (tag != -1) {
                    reader.readBytes();
                }
            } else {
                ProtoReader reader = new ProtoReader(new Buffer().write(bytes));
                reader.beginMessage();
                int tag = reader.nextTag();
                if (valid) {
                    if (tag != 1 || reader.readVarint32() != 150 || reader.nextTag() != -1) {
                        throw new AssertionError("valid scalar changed");
                    }
                } else if (tag != -1) {
                    reader.readBytes();
                }
            }
            if (!valid) {
                throw new AssertionError("malformed input accepted");
            }
            System.out.println("PASS " + fast + " " + name);
        } catch (IOException expected) {
            if (valid) {
                failures++;
                System.out.println("FAIL " + fast + " " + name + " valid input rejected");
            } else {
                System.out.println("PASS " + fast + " " + name + " rejected with IOException");
            }
        } catch (Throwable unexpected) {
            failures++;
            System.out.println("FAIL " + fast + " " + name + " " + unexpected.getClass().getName());
        }
    }

    public static void main(String[] args) {
        for (boolean fast : new boolean[] {false, true}) {
            check(fast, "valid-scalar", "089601", true);
            check(fast, "negative-length-skipped-group", "0b1280ffffff0f0c", false);
            check(fast, "positive-length-overflow", "0affffffff07", false);
        }
        if (failures != 0) {
            throw new AssertionError("reader checks failed: " + failures);
        }
    }
}
