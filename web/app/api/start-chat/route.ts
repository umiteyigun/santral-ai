import { AccessToken, RoomServiceClient, AgentDispatchClient } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
    // Generate random room name
    const roomName = `sohbet-${Math.random().toString(36).substring(2, 15)}`;
    const participantName = req.nextUrl.searchParams.get('name') || 'Kullanici';

    const apiKey = process.env.LIVEKIT_API_KEY || 'devkey';
    const apiSecret = process.env.LIVEKIT_API_SECRET || 'secret';
    const livekitUrl = process.env.LIVEKIT_URL || 'http://livekit:7880';

    try {
        // Create room
        const roomService = new RoomServiceClient(livekitUrl, apiKey, apiSecret);
        await roomService.createRoom({
            name: roomName,
        });

        // Create token for user
        const at = new AccessToken(apiKey, apiSecret, {
            identity: participantName,
        });
        at.addGrant({ roomJoin: true, room: roomName, canPublish: true, canSubscribe: true });
        const jwt = await at.toJwt();

        // Dispatch agent to room
        const agentDispatchClient = new AgentDispatchClient(livekitUrl, apiKey, apiSecret);
        await agentDispatchClient.createDispatch(roomName, "voice-assistant", {});
        
        console.log(`✅ Room created: ${roomName}, Agent dispatched`);

        // Determine WebSocket protocol
        const host = req.headers.get('host') || 'localhost';
        const protocol = req.headers.get('x-forwarded-proto') || 
                         (req.url.startsWith('https') ? 'https' : 'http');
        const wsProtocol = protocol === 'https' ? 'wss' : 'ws';
        
        const serverUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 
                         `${wsProtocol}://${host}/livekit`;

        return NextResponse.json({ 
            token: jwt, 
            serverUrl,
            roomName 
        });
    } catch (error: any) {
        console.error('Error starting chat:', error.message);
        return NextResponse.json(
            { error: 'Failed to start chat: ' + error.message },
            { status: 500 }
        );
    }
}

