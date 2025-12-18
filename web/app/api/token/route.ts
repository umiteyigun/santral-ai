import { AccessToken } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
    // This endpoint is kept for backward compatibility but is not used anymore
    // Use /api/start-chat instead
    const roomName = req.nextUrl.searchParams.get('room') || 'sohbet-odasi';
    const participantName = req.nextUrl.searchParams.get('name') || 'Misafir-' + Math.floor(Math.random() * 1000);

    const apiKey = process.env.LIVEKIT_API_KEY || 'devkey';
    const apiSecret = process.env.LIVEKIT_API_SECRET || 'secret';

    const at = new AccessToken(apiKey, apiSecret, {
        identity: participantName,
    });

    at.addGrant({ roomJoin: true, room: roomName, canPublish: true, canSubscribe: true });
    const jwt = await at.toJwt();

    // Determine WebSocket protocol based on request protocol
    const host = req.headers.get('host') || 'localhost';
    const protocol = req.headers.get('x-forwarded-proto') || 
                     (req.url.startsWith('https') ? 'https' : 'http');
    const wsProtocol = protocol === 'https' ? 'wss' : 'ws';
    
    const serverUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 
                     `${wsProtocol}://${host}/livekit`;

    return NextResponse.json({ token: jwt, serverUrl });
}

