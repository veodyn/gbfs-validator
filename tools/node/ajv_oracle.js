// Run tests/fixtures/ajv/cases.json through upstream's own validate.js and
// dump the resulting error arrays. Those dumps are the engine's oracle.
const path = require('path')
const fs = require('fs')
const writeMeta = require('./write_meta')

const root = path.join(__dirname, '..', '..')
const validate = require(path.join(root, 'upstream/gbfs-validator/validate.js'))

const casesPath = path.join(root, 'tests/fixtures/ajv/cases.json')
const cases = JSON.parse(fs.readFileSync(casesPath))

const out = {}
for (const c of cases) {
  const schema = c.schemaFile
    ? JSON.parse(
        fs.readFileSync(path.join(root, 'src/gbfs_validator/data/schemas', c.schemaFile))
      )
    : c.schema
  let result
  try {
    result = validate(schema, c.data, { addSchema: c.addSchema || [] })
  } catch (err) {
    out[c.name] = { threw: String(err.message) }
    continue
  }
  out[c.name] = result.errors
}

fs.writeFileSync(
  path.join(root, 'tests/fixtures/ajv/goldens.json'),
  JSON.stringify(out, null, 2) + '\n'
)
console.log(`wrote ${Object.keys(out).length} goldens`)
writeMeta()
