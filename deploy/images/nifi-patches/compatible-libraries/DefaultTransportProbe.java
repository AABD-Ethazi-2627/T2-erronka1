import com.rabbitmq.client.*;
import javax.net.ssl.SSLContext;

/** This class and its helper contain no Netty types: execute with no Netty JARs. */
public class DefaultTransportProbe {
    static class Factory extends ConnectionFactory {
        String handler() throws Exception {return createFrameHandlerFactory().getClass().getName();}
    }
    public static void main(String[] args) throws Exception {
        try {Class.forName("io.netty.channel.Channel");throw new AssertionError("Netty unexpectedly available");}
        catch(ClassNotFoundException expected){}
        Factory f=new Factory();
        TransportFixture.check(f.handler().equals("com.rabbitmq.client.impl.SocketFrameHandlerFactory"),"default blocking transport");
        TransportFixture.exercise(f,false);
        TransportFixture.exercise(new Factory(),false,true);
        TransportFixture.exercise(new Factory(),true);
        Factory nio=new Factory();nio.useNio();
        TransportFixture.check(nio.handler().equals("com.rabbitmq.client.impl.nio.SocketChannelFrameHandlerFactory"),"JDK NIO transport");
        TransportFixture.exercise(nio,false);
        Factory tls=new Factory();tls.useSslProtocol(SSLContext.getDefault());
        TransportFixture.check(tls.isSSL(),"JDK TLS configuration without Netty");
        TransportFixture.check(tls.handler().equals("com.rabbitmq.client.impl.SocketFrameHandlerFactory"),"TLS blocking factory");
        // Activation should fail without its optional-at-execution Netty classes.
        try {Factory missing=new Factory();missing.netty();missing.handler();throw new AssertionError("Netty activation succeeded without Netty");}
        catch(NoClassDefFoundError expected){TransportFixture.check(expected.getMessage().startsWith("io/netty/"),"missing Netty cause");}
        System.out.println("PASS no-Netty default handshake/channel/publish/close; JDK NIO; malformed peer; TLS init; absent-Netty activation control");
    }
}
