# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

from proto import bully_pb2 as proto_dot_bully__pb2

GRPC_GENERATED_VERSION = '1.73.1'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in proto/bully_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class BullyServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Eleccion = channel.unary_unary(
                '/BullyService/Eleccion',
                request_serializer=proto_dot_bully__pb2.EleccionRequest.SerializeToString,
                response_deserializer=proto_dot_bully__pb2.EleccionReply.FromString,
                _registered_method=True)
        self.Coordinador = channel.unary_unary(
                '/BullyService/Coordinador',
                request_serializer=proto_dot_bully__pb2.CoordinadorRequest.SerializeToString,
                response_deserializer=proto_dot_bully__pb2.CoordinadorReply.FromString,
                _registered_method=True)
        self.Heartbeat = channel.unary_unary(
                '/BullyService/Heartbeat',
                request_serializer=proto_dot_bully__pb2.HeartbeatRequest.SerializeToString,
                response_deserializer=proto_dot_bully__pb2.HeartbeatReply.FromString,
                _registered_method=True)
        self.Respuesta = channel.unary_unary(
                '/BullyService/Respuesta',
                request_serializer=proto_dot_bully__pb2.RespuestaRequest.SerializeToString,
                response_deserializer=proto_dot_bully__pb2.RespuestaReply.FromString,
                _registered_method=True)


class BullyServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Eleccion(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Coordinador(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Heartbeat(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Respuesta(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_BullyServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Eleccion': grpc.unary_unary_rpc_method_handler(
                    servicer.Eleccion,
                    request_deserializer=proto_dot_bully__pb2.EleccionRequest.FromString,
                    response_serializer=proto_dot_bully__pb2.EleccionReply.SerializeToString,
            ),
            'Coordinador': grpc.unary_unary_rpc_method_handler(
                    servicer.Coordinador,
                    request_deserializer=proto_dot_bully__pb2.CoordinadorRequest.FromString,
                    response_serializer=proto_dot_bully__pb2.CoordinadorReply.SerializeToString,
            ),
            'Heartbeat': grpc.unary_unary_rpc_method_handler(
                    servicer.Heartbeat,
                    request_deserializer=proto_dot_bully__pb2.HeartbeatRequest.FromString,
                    response_serializer=proto_dot_bully__pb2.HeartbeatReply.SerializeToString,
            ),
            'Respuesta': grpc.unary_unary_rpc_method_handler(
                    servicer.Respuesta,
                    request_deserializer=proto_dot_bully__pb2.RespuestaRequest.FromString,
                    response_serializer=proto_dot_bully__pb2.RespuestaReply.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'BullyService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('BullyService', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class BullyService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Eleccion(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/BullyService/Eleccion',
            proto_dot_bully__pb2.EleccionRequest.SerializeToString,
            proto_dot_bully__pb2.EleccionReply.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Coordinador(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/BullyService/Coordinador',
            proto_dot_bully__pb2.CoordinadorRequest.SerializeToString,
            proto_dot_bully__pb2.CoordinadorReply.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Heartbeat(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/BullyService/Heartbeat',
            proto_dot_bully__pb2.HeartbeatRequest.SerializeToString,
            proto_dot_bully__pb2.HeartbeatReply.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Respuesta(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/BullyService/Respuesta',
            proto_dot_bully__pb2.RespuestaRequest.SerializeToString,
            proto_dot_bully__pb2.RespuestaReply.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
