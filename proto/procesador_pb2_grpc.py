# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

from proto import procesador_pb2 as proto_dot_procesador__pb2

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
        + f' but the generated code in proto/procesador_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class ProcesadorImagenStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.ProcesarImagen = channel.unary_unary(
                '/ProcesadorImagen/ProcesarImagen',
                request_serializer=proto_dot_procesador__pb2.ImagenRequest.SerializeToString,
                response_deserializer=proto_dot_procesador__pb2.ImagenReply.FromString,
                _registered_method=True)


class ProcesadorImagenServicer(object):
    """Missing associated documentation comment in .proto file."""

    def ProcesarImagen(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_ProcesadorImagenServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'ProcesarImagen': grpc.unary_unary_rpc_method_handler(
                    servicer.ProcesarImagen,
                    request_deserializer=proto_dot_procesador__pb2.ImagenRequest.FromString,
                    response_serializer=proto_dot_procesador__pb2.ImagenReply.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'ProcesadorImagen', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('ProcesadorImagen', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class ProcesadorImagen(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def ProcesarImagen(request,
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
            '/ProcesadorImagen/ProcesarImagen',
            proto_dot_procesador__pb2.ImagenRequest.SerializeToString,
            proto_dot_procesador__pb2.ImagenReply.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
