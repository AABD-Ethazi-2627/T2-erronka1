import com.squareup.wire.ByteArrayProtoReader32;
import com.squareup.wire.ProtoAdapter;
import com.squareup.wire.ProtoReader;
import com.squareup.wire.schema.Location;
import com.squareup.wire.schema.Schema;
import com.squareup.wire.schema.SchemaLoader;
import java.io.IOException;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import okio.Buffer;

/** Tests real upstream reader classes and the unchanged Wire-schema 5 consumer. */
public final class Wire5ReaderRegression {
  interface Checked { void run() throws Exception; }
  static int failed, passed;
  static void require(boolean value) { if (!value) throw new AssertionError("unexpected value"); }
  static void test(String name, Checked action) {
    try { action.run(); passed++; System.out.println("PASS " + name); }
    catch (Throwable error) { failed++; System.out.println("FAIL " + name + " " + error); }
  }
  static byte[] hex(String text) { return java.util.HexFormat.of().parseHex(text); }
  static final class Reader {
    final ProtoReader stream;
    final ByteArrayProtoReader32 array;
    Reader(boolean fast, String text) {
      byte[] bytes = hex(text);
      stream = fast ? null : new ProtoReader(new Buffer().write(bytes));
      array = fast ? new ByteArrayProtoReader32(bytes, 0, bytes.length) : null;
    }
    long begin() throws IOException { return stream != null ? stream.beginMessage() : array.beginMessage(); }
    int next() throws IOException { return stream != null ? stream.nextTag() : array.nextTag(); }
    int int32() throws IOException { return stream != null ? stream.readVarint32() : array.readVarint32(); }
    int fixed32() throws IOException { return stream != null ? stream.readFixed32() : array.readFixed32(); }
    long fixed64() throws IOException { return stream != null ? stream.readFixed64() : array.readFixed64(); }
    String string() throws IOException { return stream != null ? stream.readString() : array.readString(); }
    void bytes() throws IOException { if (stream != null) stream.readBytes(); else array.readBytes(); }
    void skip() throws IOException { if (stream != null) stream.skip(); else array.skip(); }
    long minimum() { return stream != null ? stream.nextFieldMinLengthInBytes() : array.nextFieldMinLengthInBytes(); }
    void end(long token) throws IOException {
      if (stream != null) stream.endMessageAndGetUnknownFields(token);
      else array.endMessageAndGetUnknownFields((int) token);
    }
  }
  static void rejectsIO(Checked action) throws Exception {
    try { action.run(); }
    catch (IOException expected) { return; }
    throw new AssertionError("malformed input accepted or crossed logical limit");
  }
  public static void main(String[] args) throws Exception {
    for (boolean fast : new boolean[] {false, true}) {
      String prefix = fast ? "array/" : "stream/";
      test(prefix + "valid-scalar-roundtrip", () -> {
        Reader r = new Reader(fast, "08960112036361741d78563412210807060504030201");
        long t=r.begin(); require(r.next()==1); require(r.int32()==150);
        require(r.next()==2); require(r.string().equals("cat"));
        require(r.next()==3); require(r.fixed32()==0x12345678);
        require(r.next()==4); require(r.fixed64()==0x0102030405060708L);
        require(r.next()==-1); r.end(t);
      });
      test(prefix + "valid-skipped-group", () -> {
        Reader r=new Reader(fast,"0b12017f0c0801"); long t=r.begin();
        require(r.next()==1); require(r.int32()==1); require(r.next()==-1); r.end(t);
      });
      test(prefix + "negative-length-in-skipped-group", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0b12ffffffff0f0c"); r.begin(); r.next();
      }));
      test(prefix + "positive-length-overflow", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0affffffff07"); r.begin(); r.next(); r.bytes();
      }));
      test(prefix + "nested-varint-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a010801"); r.begin(); require(r.next()==1);
        r.begin(); require(r.next()==1); r.int32();
      }));
      test(prefix + "nested-fixed32-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a010d01020304"); r.begin(); require(r.next()==1);
        r.begin(); require(r.next()==1); r.fixed32();
      }));
      test(prefix + "nested-fixed64-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a01090102030405060708"); r.begin(); require(r.next()==1);
        r.begin(); require(r.next()==1); r.fixed64();
      }));
      test(prefix + "truncated-varint", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0880"); r.begin(); require(r.next()==1); r.int32();
      }));
      test(prefix + "negative-128-advisory", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0b1280ffffff0f0c"); r.begin(); r.next();
      }));
      test(prefix + "valid-nested-exact-boundary", () -> {
        Reader r=new Reader(fast,"0a0208011002");long parent=r.begin();require(r.next()==1);
        long child=r.begin();require(r.next()==1);require(r.int32()==1);require(r.next()==-1);r.end(child);
        require(r.next()==2);require(r.int32()==2);require(r.next()==-1);r.end(parent);
      });
      test(prefix + "valid-empty-string", () -> {
        Reader r=new Reader(fast,"0a00");long token=r.begin();require(r.next()==1);
        require(r.string().isEmpty());require(r.next()==-1);r.end(token);
      });
      test(prefix + "valid-packed-varints", () -> {
        Reader r=new Reader(fast,"0a03019601");long token=r.begin();require(r.next()==1);require(r.int32()==1);
        require(r.next()==1);require(r.int32()==150);require(r.next()==-1);r.end(token);
      });
      test(prefix + "valid-packed-fixed32", () -> {
        Reader r=new Reader(fast,"0a087856341201000000");long token=r.begin();require(r.next()==1);
        require(r.fixed32()==0x12345678);require(r.next()==1);require(r.fixed32()==1);require(r.next()==-1);r.end(token);
      });
      test(prefix + "valid-ten-byte-varint", () -> {
        Reader r=new Reader(fast,"08ffffffffffffffffff01");long token=r.begin();require(r.next()==1);
        require(r.int32()==-1);require(r.next()==-1);r.end(token);
      });
      test(prefix + "nested-tag-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a018001");r.begin();r.next();r.begin();r.next();
      }));
      test(prefix + "nested-string-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a020a03636174");r.begin();r.next();r.begin();r.next();r.string();
      }));
      test(prefix + "nested-skip-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a020a03636174");r.begin();r.next();r.begin();r.next();r.skip();
      }));
      test(prefix + "nested-group-must-not-read-parent", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a030b12036162630c");r.begin();r.next();r.begin();r.next();
      }));
      test(prefix + "packed-truncated-fixed32", () -> rejectsIO(() -> {
        Reader r=new Reader(fast,"0a0301020304");r.begin();r.next();r.fixed32();
      }));
      test(prefix + "large-valid-packed-capacity-is-not-truncation", () -> {
        byte[] data=new byte[70004];data[0]=10;data[1]=(byte)0xf0;data[2]=(byte)0xa2;data[3]=4;
        Arrays.fill(data,4,data.length,(byte)1);Reader r=new Reader(fast,java.util.HexFormat.of().formatHex(data));
        long token=r.begin();require(r.next()==1);
        int count=0;do {require(r.int32()==1);count++;}while(r.next()!=-1);require(count==70000);r.end(token);
      });
      test(prefix + "seeded-corpus-checked-decode-failures", () -> {
        java.util.Random random=new java.util.Random(20261104);
        for(int i=0;i<512;i++) {
          byte[] data=new byte[random.nextInt(33)];random.nextBytes(data);
          Reader r=new Reader(fast,java.util.HexFormat.of().formatHex(data));
          try {long token=r.begin();int steps=0;while(r.next()!=-1){require(++steps<=64);r.skip();}r.end(token);}
          catch(IOException expected) { /* The documented malformed-input path. */ }
        }
      });
    }
    test("stream/untrusted-length-cannot-drive-preallocation", () -> {
      Reader r=new Reader(false,"0affffffff07");r.begin();r.next();require(r.minimum()<=65536);
    });
    test("schema5/actual-runtime-message-adapter-roundtrip", () -> {
      Path root=Files.createTempDirectory("wire5-schema-regression-");
      try {
        Files.writeString(root.resolve("sample.proto"),
          "syntax = \"proto2\"; package local; message Sample { optional int32 n = 1; optional string s = 2; }");
        SchemaLoader loader=new SchemaLoader(FileSystems.getDefault());
        loader.initRoots(Collections.singletonList(Location.get(root.toString())), Collections.emptyList());
        Schema schema=loader.loadSchema(); ProtoAdapter<Object> adapter=schema.protoAdapter("local.Sample", true);
        Map<String,Object> message=new LinkedHashMap<>(); message.put("n",150); message.put("s","cat");
        byte[] encoded=adapter.encode(message);
        require(Arrays.equals(encoded,hex("0896011203636174")));
        require(adapter.decode(encoded).equals(message));
      } finally { Files.deleteIfExists(root.resolve("sample.proto")); Files.deleteIfExists(root); }
    });
    System.out.println("RESULT passed="+passed+" failed="+failed);
    if (failed != 0) System.exit(1);
  }
}
