from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from docia.tracking.serializers import TrackingEventSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tracking_event_view(request):
    serializer = TrackingEventSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        serializer.save()
        # Return 204 No Content status (no response body)
        return Response(status=status.HTTP_204_NO_CONTENT)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
