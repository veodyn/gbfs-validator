// Provenance for every committed golden: which Node, which upstream pin,
// which lockfile. Each golden generator calls this so the record cannot go
// stale behind whichever one happened to run last.
const path = require('path')
const fs = require('fs')
const crypto = require('crypto')

const root = path.join(__dirname, '..', '..')

function writeMeta() {
  const pins = fs.readFileSync(path.join(root, 'src/gbfs_validator/data/PIN'), 'utf8').split('\n')
  const lock = fs.readFileSync(path.join(root, 'upstream/yarn.lock'))
  fs.writeFileSync(
    path.join(root, 'tests/fixtures/META.json'),
    JSON.stringify(
      {
        node: process.version,
        upstreamPin: pins[0].trim(),
        schemaPin: pins[1].trim(),
        yarnLockSha256: crypto.createHash('sha256').update(lock).digest('hex'),
      },
      null,
      2
    ) + '\n'
  )
}

module.exports = writeMeta
