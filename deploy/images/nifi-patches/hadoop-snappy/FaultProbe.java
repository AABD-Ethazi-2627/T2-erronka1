import java.util.Arrays;
import org.apache.hadoop.io.compress.snappy.SnappyCompressor;
import org.xerial.snappy.Snappy;

/** Test post-failure state without invoking native code. */
public final class FaultProbe {
  public static void main(String[] args) throws Exception {
    int cases=0;
    for (String kind:new String[]{"io","runtime","error"}) {
      for (boolean partial:new boolean[]{false,true}) {
        if (partial && args[0].equals("original")) continue;
        Snappy.arm(kind,partial);
        SnappyCompressor c=new SnappyCompressor(4096);
        byte[] input=new byte[100], output=new byte[8192];
        c.setInput(input,0,input.length); c.finish();
        if(c.compress(output,0,output.length)!=64) throw new AssertionError("positive control");
        c.reset(); c.setInput(input,0,input.length); c.finish();
        boolean caught=false;
        try { c.compress(output,0,output.length); }
        catch(java.io.IOException | RuntimeException | Error failure) {
          if(!"synthetic fault".equals(failure.getMessage())) throw failure;
          caught=true;
        }
        if(!caught) throw new AssertionError("fault control did not throw");
        Arrays.fill(output,(byte)0);
        int n=c.compress(output,0,output.length);
        if(n!=0 || c.getBytesWritten()!=0 || !c.finished() || !c.needsInput())
          throw new AssertionError("stale output/state after "+kind+" partial="+partial+" bytes="+n);
        for(byte value:output) if(value!=0) throw new AssertionError("stale byte");
        c.reset();
        if(c.finished() || !c.needsInput() || c.getBytesWritten()!=0)
          throw new AssertionError("reset after fault");
        cases++;
      }
    }
    System.out.println("PASS synthetic non-native faults="+cases+" stale output=0");
  }
}
