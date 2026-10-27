#!/usr/bin/env bash
# Prepare private lab certificates outside the repository; never overwrites them.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 SERVER_LAN_IP NEW_PRIVATE_OUTPUT_DIRECTORY" >&2
  exit 2
fi

server_ip=$1
destination=$2
python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$server_ip"
if [[ -e "$destination" ]]; then
  echo "Output directory already exists; refusing to overwrite certificates" >&2
  exit 1
fi

umask 077
mkdir -m 700 "$destination"
mkdir -m 700 "$destination/private" "$destination/gateway" "$destination/clients"

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$destination/private/ca.key"
openssl req -new -x509 -sha256 -days 365 -key "$destination/private/ca.key" \
  -subj '/CN=CNC Guard Lab Client CA' -out "$destination/private/ca.crt" \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign'

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$destination/private/server.key"
openssl req -new -key "$destination/private/server.key" \
  -subj "/CN=$server_ip" -out "$destination/private/server.csr"
cat > "$destination/private/server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:$server_ip
EOF
openssl x509 -req -sha256 -days 90 -in "$destination/private/server.csr" \
  -CA "$destination/private/ca.crt" -CAkey "$destination/private/ca.key" \
  -CAcreateserial -extfile "$destination/private/server.ext" \
  -out "$destination/private/server.crt"
cat "$destination/private/server.crt" "$destination/private/server.key" > "$destination/gateway/server.pem"
cp "$destination/private/ca.crt" "$destination/gateway/clients-ca.pem"

cat > "$destination/private/client.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
EOF
for student in 1 2 3 4; do
  name="student-$student"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$destination/private/$name.key"
  openssl req -new -key "$destination/private/$name.key" \
    -subj "/CN=cnc-$name" -out "$destination/private/$name.csr"
  openssl x509 -req -sha256 -days 90 -in "$destination/private/$name.csr" \
    -CA "$destination/private/ca.crt" -CAkey "$destination/private/ca.key" \
    -CAserial "$destination/private/ca.srl" -extfile "$destination/private/client.ext" \
    -out "$destination/clients/$name.crt"
  cp "$destination/private/$name.key" "$destination/clients/$name.key"
done
cp "$destination/private/ca.crt" "$destination/clients/ca.crt"
echo "Created private gateway and four client certificates in $destination"
