// GHSA-5x38-2vff-x55p: deprecated OIDs must not override real basicConstraints.
const assert = require('node:assert/strict');
const forge = require(process.argv[2] || '/usr/share/kibana/node_modules/node-forge');
const keys = forge.pki.rsa.generateKeyPair(1024); // disposable regression keys only
function cert(name, issuer, serial, extensions) {
  const c = forge.pki.createCertificate();
  c.publicKey = keys.publicKey;
  c.serialNumber = serial;
  c.validity.notBefore = new Date('2020-01-01');
  c.validity.notAfter = new Date('2040-01-01');
  c.setSubject([{name: 'commonName', value: name}]);
  c.setIssuer([{name: 'commonName', value: issuer}]);
  c.setExtensions(extensions);
  c.sign(keys.privateKey, forge.md.sha256.create());
  return forge.pki.certificateFromPem(forge.pki.certificateToPem(c));
}
const root = cert('root', 'root', '01', [{name: 'basicConstraints', cA: true}]);
const leaf = cert('leaf', 'intermediate', '03', [{name: 'basicConstraints', cA: false}]);
function verify(intermediate) {
  return forge.pki.verifyCertificateChain(forge.pki.createCaStore([root]), [leaf, intermediate]);
}
assert.equal(verify(cert('intermediate', 'root', '02', [{name: 'basicConstraints', cA: true}])), true);
for (const id of ['2.5.29.10', '2.5.29.13']) {
  const value = forge.asn1.toDer(forge.asn1.create(forge.asn1.Class.UNIVERSAL,
    forge.asn1.Type.SEQUENCE, true, [forge.asn1.create(forge.asn1.Class.UNIVERSAL,
      forge.asn1.Type.BOOLEAN, false, '\xff')])).getBytes();
  const intermediate = cert('intermediate', 'root', '02', [
    {id, value}, {name: 'basicConstraints', cA: false},
  ]);
  assert.throws(() => verify(intermediate));
}
const md = forge.md.sha256.create(); md.update('valid-signature');
assert.equal(keys.publicKey.verify(md.digest().bytes(), keys.privateKey.sign(md)), true);
console.log('node-forge: valid chain/signature accepted; both deprecated-OID bypasses rejected');
