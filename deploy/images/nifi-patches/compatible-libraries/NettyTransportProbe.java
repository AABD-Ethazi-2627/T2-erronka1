import com.rabbitmq.client.*;
import io.netty.buffer.*;
import io.netty.channel.*;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.handler.codec.*;
import io.netty.handler.ssl.*;
import java.util.concurrent.*;
import javax.net.ssl.SSLEngine;

public class NettyTransportProbe {
    static class Factory extends ConnectionFactory {
        String handler() throws Exception {return createFrameHandlerFactory().getClass().getName();}
    }
    static void embedded() {
        // Real Netty decoder under bounded fragmented/oversize input; AMQP's documented length layout.
        var ch=new EmbeddedChannel(new LengthFieldBasedFrameDecoder(4096,3,4,1,0));
        try {
            TransportFixture.check(!ch.writeInbound(Unpooled.wrappedBuffer(new byte[]{1,0,0,0})),"fragment buffered");
            TransportFixture.check(ch.writeInbound(Unpooled.wrappedBuffer(new byte[]{0,0,0,(byte)206})),"frame emitted");
            ByteBuf frame=ch.readInbound();try{TransportFixture.check(frame.readableBytes()==8,"frame bytes");}finally{frame.release();}
            try {ch.writeInbound(Unpooled.wrappedBuffer(new byte[]{1,0,0,0,0,0x20,0}));throw new AssertionError("oversize accepted");}
            catch(TooLongFrameException expected){}
        } finally {ch.finishAndReleaseAll();}
    }
    public static void main(String[] args) throws Exception {
        embedded();
        EventLoopGroup group=new NioEventLoopGroup(1);
        var seen=new java.util.concurrent.atomic.AtomicInteger();
        try {
            for(boolean malformed:new boolean[]{false,true}) {
                Factory f=new Factory();f.netty().eventLoopGroup(group).channelCustomizer(ch->{
                    TransportFixture.check(ch.getClass().getName().contains("NioSocketChannel"),"JDK NIO Netty channel");
                    seen.incrementAndGet();
                });
                TransportFixture.check(f.handler().equals("com.rabbitmq.client.impl.NettyFrameHandlerFactory"),"actual Netty frame factory");
                TransportFixture.exercise(f,malformed);
            }
            TransportFixture.check(seen.get()==2,"both real Netty channels initialized");
            SslContext tls=SslContextBuilder.forClient().sslProvider(SslProvider.JDK).build();
            SSLEngine engine=tls.newEngine(UnpooledByteBufAllocator.DEFAULT);engine.beginHandshake();engine.closeOutbound();
            TransportFixture.check(engine.getClass().getName().contains("SSLEngine"),"JDK TLS engine");
            System.out.println("PASS Netty embedded fragmented/oversize controls; AMQP handshake/channel/publish/close; malformed peer; JDK TLS init; NIO (no native transport)");
        } finally {group.shutdownGracefully(0,2,TimeUnit.SECONDS).sync();}
    }
}
