import com.amazonaws.services.schemaregistry.utils.apicurio.FileDescriptorUtils;
import com.amazonaws.services.schemaregistry.utils.apicurio.ProtobufSchemaLoader;
import com.google.protobuf.DescriptorProtos;

/** Normal AWS consumer input exercises the constructor changed by Wire6. */
public final class AWSConsumerProbe {
    public static void main(String[] args) throws Exception {
        for (String syntax : new String[] {"proto2", "proto3"}) {
          for (byte legacyOption : new byte[] {0, 1}) {
            var field = DescriptorProtos.FieldDescriptorProto.newBuilder()
                    .setName("value").setNumber(1)
                    .setType(DescriptorProtos.FieldDescriptorProto.Type.TYPE_STRING)
                    .setLabel(DescriptorProtos.FieldDescriptorProto.Label.LABEL_OPTIONAL);
            var message = DescriptorProtos.DescriptorProto.newBuilder().setName("Event").addField(field);
            var file = DescriptorProtos.FileDescriptorProto.newBuilder().setName("event.proto")
                    .setPackage("cnc.closeout").setSyntax(syntax).addMessageType(message)
                    .setOptions(DescriptorProtos.FileOptions.parseFrom(new byte[] {(byte) 0xd0, 0x02, legacyOption}))
                    .build();
            var element = FileDescriptorUtils.fileDescriptorToProtoFile(file);
            ProtobufSchemaLoader.loadSchema(java.util.Optional.of("cnc.closeout"), "event.proto", element.toSchema());
            if (!element.toSchema().contains("string value = 1")) {
                throw new AssertionError("schema field changed: " + syntax);
            }
            var restored = FileDescriptorUtils.protoFileToFileDescriptor(element, "event.proto");
            if (!restored.findMessageTypeByName("Event").findFieldByNumber(1).getName().equals("value")) {
                throw new AssertionError("descriptor roundtrip changed: " + syntax);
            }
            String expected = "php_generic_services = " + (legacyOption == 1 ? "true" : "false");
            if (!element.toSchema().contains(expected)
                    || !FileDescriptorUtils.fileDescriptorToProtoFile(restored.toProto()).toSchema().contains(expected)) {
                throw new AssertionError("legacy PHP option lost: " + syntax + " " + legacyOption);
            }
            System.out.println("PASS AWS descriptor roundtrip " + syntax + " PHP=" + legacyOption);
          }
        }
    }
}
