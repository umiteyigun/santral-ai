import { AgentDispatchClient } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
    const { roomName } = await req.json();
    
    if (!roomName) {
        return NextResponse.json(
            { error: 'roomName is required' },
            { status: 400 }
        );
    }

    const apiKey = process.env.LIVEKIT_API_KEY || 'devkey';
    const apiSecret = process.env.LIVEKIT_API_SECRET || 'secret';
    const livekitUrl = process.env.LIVEKIT_URL || 'http://livekit:7880';

    try {
        // Dispatch agent to existing room
        const agentDispatchClient = new AgentDispatchClient(livekitUrl, apiKey, apiSecret);
        await agentDispatchClient.createDispatch(roomName, "voice-assistant", {});
        
        console.log(`✅ Agent dispatched to room: ${roomName}`);

        return NextResponse.json({ 
            success: true,
            roomName 
        });
    } catch (error: any) {
        console.error('Error dispatching agent:', error.message);
        return NextResponse.json(
            { error: 'Failed to dispatch agent: ' + error.message },
            { status: 500 }
        );
    }
}

