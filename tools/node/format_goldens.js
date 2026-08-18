const path = require('path')
const fs = require('fs')
const writeMeta = require('./write_meta')
const { createRequire } = require('module')
const root = path.join(__dirname, '..', '..')
const req = createRequire(path.join(root, 'upstream/gbfs-validator/validate.js'))
const Ajv = req('ajv')
const addFormats = req('ajv-formats')
const ajv = new Ajv({ allErrors: true, strict: false })
addFormats(ajv)
const corpus = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/formats/corpus.json')))
const out = {}
for (const [format, samples] of Object.entries(corpus)) {
  const check = ajv.compile({ type: 'string', format })
  out[format] = Object.fromEntries(samples.map(s => [s, check(s)]))
}
fs.writeFileSync(path.join(root, 'tests/fixtures/formats/goldens.json'), JSON.stringify(out, null, 2))
writeMeta()
