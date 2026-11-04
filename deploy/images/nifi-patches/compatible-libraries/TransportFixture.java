import com.rabbitmq.client.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Fixed-size AMQP handshake/channel/publish fixture, not a broker. Binds IPv4 loopback only. */
public final class TransportFixture implements AutoCloseable {
    static final byte[] MESSAGE="bounded-fixture-publish".getBytes(StandardCharsets.US_ASCII);
    final ServerSocket server;
    final ExecutorService worker=Executors.newSingleThreadExecutor();
    final Future<?> result;
    TransportFixture(boolean malformed) throws IOException {
        server=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));server.setSoTimeout(3000);
        result=worker.submit(()->{try(Socket s=server.accept()) {
            s.setSoTimeout(3000);
            var in=new DataInputStream(s.getInputStream());var out=new DataOutputStream(s.getOutputStream());
            check(Arrays.equals(in.readNBytes(8),new byte[]{65,77,81,80,0,0,9,1}),"protocol header");
            if(malformed) {
                // A small invalid protocol version response; no huge length/allocation.
                out.write(new byte[]{65,77,81,80,0,0,0,0});out.flush();return;
            }
            var start=new ByteArrayOutputStream();var fields=new DataOutputStream(start);
            fields.writeByte(0);fields.writeByte(9);fields.writeInt(0);
            longstr(fields,"PLAIN");longstr(fields,"en_US");
            method(out,0,10,10,start.toByteArray());
            expectMethod(in,0,10,11); // start-ok: fixture credentials not retained/logged
            var tune=new ByteArrayOutputStream();var t=new DataOutputStream(tune);
            t.writeShort(8);t.writeInt(4096);t.writeShort(0);method(out,0,10,30,tune.toByteArray());
            expectMethod(in,0,10,31);expectMethod(in,0,10,40);method(out,0,10,41,new byte[]{0});
            expectMethod(in,1,20,10);method(out,1,20,11,new byte[4]);
            expectMethod(in,1,60,40);
            Packet header=packet(in);check(header.type==2 && header.channel==1,"publish content header");
            Packet body=packet(in);check(body.type==3 && body.channel==1 && Arrays.equals(body.payload,MESSAGE),"publish body");
            expectMethod(in,1,20,40);method(out,1,20,41,new byte[0]);
            expectMethod(in,0,10,50);method(out,0,10,51,new byte[0]);
        }catch(Exception e){throw new CompletionException(e);}});
    }
    record Packet(int type,int channel,byte[] payload){}
    static Packet packet(DataInputStream in) throws IOException {
        int type=in.readUnsignedByte(),channel=in.readUnsignedShort(),length=in.readInt();
        check(length>=0 && length<=4096,"fixture frame cap");byte[] payload=in.readNBytes(length);
        check(payload.length==length && in.readUnsignedByte()==206,"frame end");return new Packet(type,channel,payload);
    }
    static void expectMethod(DataInputStream in,int channel,int cls,int method) throws IOException {
        Packet p=packet(in);check(p.type==1 && p.channel==channel && p.payload.length>=4,"method frame");
        var b=new DataInputStream(new ByteArrayInputStream(p.payload));check(b.readUnsignedShort()==cls && b.readUnsignedShort()==method,"method id");
    }
    static void longstr(DataOutputStream out,String s) throws IOException {byte[] b=s.getBytes(StandardCharsets.US_ASCII);out.writeInt(b.length);out.write(b);}
    static void method(DataOutputStream out,int channel,int cls,int method,byte[] args) throws IOException {
        out.writeByte(1);out.writeShort(channel);out.writeInt(4+args.length);out.writeShort(cls);out.writeShort(method);out.write(args);out.writeByte(206);out.flush();
    }
    static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static void configure(ConnectionFactory f) {
        f.setHost("127.0.0.1");f.setConnectionTimeout(2000);f.setHandshakeTimeout(2000);
        f.setShutdownTimeout(2000);f.setChannelRpcTimeout(2000);f.setRequestedHeartbeat(0);
        f.setAutomaticRecoveryEnabled(false);f.setUsername("fixture");f.setPassword("fixture");
        f.setMaxInboundMessageBodySize(4096);
    }
    static void exercise(ConnectionFactory factory,boolean malformed) throws Exception {exercise(factory,malformed,false);}
    static void exercise(ConnectionFactory factory,boolean malformed,boolean addresses) throws Exception {
        configure(factory);
        try(var fixture=new TransportFixture(malformed);var executor=Executors.newSingleThreadExecutor()) {
            factory.setPort(fixture.server.getLocalPort());
            if(malformed) {
                try(var c=connect(factory,executor,addresses)){throw new AssertionError("invalid version accepted");}
                catch(IOException expected) {
                    Throwable cause=expected;boolean malformedCause=false;
                    for(int depth=0;cause!=null && depth<16;depth++,cause=cause.getCause()) {
                        if(cause instanceof MalformedFrameException && cause.getMessage()!=null &&
                           cause.getMessage().contains("protocol version mismatch")) malformedCause=true;
                    }
                    check(malformedCause,"invalid peer must fail for protocol version mismatch, not transport loss");
                    System.out.println("invalid peer rejected: MalformedFrameException protocol version mismatch");
                }
            } else {
                try(Connection c=connect(factory,executor,addresses);Channel channel=c.createChannel()) {
                    check(c.isOpen() && channel.isOpen(),"connection/channel open");
                    channel.basicPublish("","fixture",null,MESSAGE);
                }
            }
            fixture.result.get(4,TimeUnit.SECONDS);
        }
    }
    static Connection connect(ConnectionFactory f,ExecutorService executor,boolean addresses) throws Exception {
        return addresses?f.newConnection(executor,new Address[]{new Address("127.0.0.1",f.getPort())}):f.newConnection(executor);
    }
    @Override public void close() throws IOException {
        server.close();worker.shutdownNow();
        try{check(worker.awaitTermination(3,TimeUnit.SECONDS),"fixture worker stopped");}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
    }
}
