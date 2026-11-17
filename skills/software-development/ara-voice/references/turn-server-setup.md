# TURN Server Setup (coturn on Hetzner)

The Pipecat runner hardcodes `stun:stun.l.google.com:19302` as the sole ICE server.
When clients are behind symmetric NAT or carrier-grade NAT, STUN fails and WebRTC
media (UDP) is blocked. The signaling/data channel (TCP) works fine, but audio tracks
die with `MediaStreamError`.

## Symptoms

Server logs:
```
WARNING - Media stream error while reading the audio; clearing track.
INFO - Discarding peer connection
```

Client: WebRTC connects (ICE completes, `bot-ready` received, data channel opens),
VAD detects speech — but no audio flows. User hears silence. Core ML pipeline is fine.

## Install coturn

```bash
ssh root@46.224.132.99
apt-get update && apt-get install -y coturn
```

## Configure

```bash
TURN_SECRET=$(openssl rand -hex 16)

cat > /etc/turnserver.conf << EOF
listening-port=3478
tls-listening-port=5349
relay-ip=46.224.132.99
external-ip=46.224.132.99
realm=ara-voice
server-name=ara-voice
lt-cred-mech
user=turnuser:${TURN_SECRET}
log-file=/var/log/coturn.log
no-cli
no-loopback-peers
no-multicast-peers
EOF

systemctl enable coturn
systemctl restart coturn

# Save for runner patching
echo "TURN_SECRET=${TURN_SECRET}" > /opt/ara-voice-agent/turn_config
```

## Open firewall

```bash
ufw allow 3478/udp
ufw allow 3478/tcp
ufw allow 5349/tcp
```

Verify: `echo test | nc -u -w2 46.224.132.99 3478 && echo reachable`

## Patch Pipecat runner

The ICE server list is hardcoded at line 636 of
`/opt/ara-voice-agent/.venv/lib/python3.11/site-packages/pipecat/runner/run.py`.

Before:
```python
iceServers=[IceServer(urls=["stun:stun.l.google.com:19302"])]
```

After:
```python
iceServers=[
    IceServer(urls=["stun:stun.l.google.com:19302"]),
    IceServer(
        urls=["turn:46.224.132.99:3478?transport=udp"],
        username="turnuser",
        credential="<TURN_SECRET>",
    ),
]
```

One-liner patch:
```bash
TURN_SECRET=$(grep TURN_SECRET /opt/ara-voice-agent/turn_config | cut -d= -f2)
RUNNER=/opt/ara-voice-agent/.venv/lib/python3.11/site-packages/pipecat/runner/run.py
python3 -c "
path = '$RUNNER'
with open(path) as f: content = f.read()
old = 'iceServers=[IceServer(urls=[\"stun:stun.l.google.com:19302\"])]'
new = '''iceServers=[
                    IceServer(urls=[\"stun:stun.l.google.com:19302\"]),
                    IceServer(
                        urls=[\"turn:46.224.132.99:3478?transport=udp\"],
                        username=\"turnuser\",
                        credential=\"${TURN_SECRET}\",
                    ),
                ]'''
content = content.replace(old, new, 1)
with open(path, 'w') as f: f.write(content)
print('Patched')
"
```

## Restart the voice agent

The patch takes effect on next server start:

```bash
fuser -k 8768/tcp
cd /opt/ara-voice-agent && source /root/.local/bin/env
nohup .venv/bin/python bot.py --whatsapp --port 8768 > /var/log/ara-voice.log 2>&1 &
```

## Important: ngrok doesn't forward UDP

The TURN server on port 3478 must be DIRECTLY reachable from the client browser.
Ngrok only tunnels TCP (HTTP/HTTPS). The Pipecat runner serves the ICE config
(including TURN credentials) over the ngrok HTTPS connection. The browser reads
the ICE config, contacts the TURN server directly at 46.224.132.99:3478, and
relays media through it.

If the firewall blocks port 3478/udp, TURN can't help — the client can't reach
the relay. Verify with `nc -u` from a remote machine or use `ufw status` on Hetzner.
