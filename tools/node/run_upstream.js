// Run the pinned upstream validator over a served fixture feed and print its
// report as JSON. The upstream CLI takes no options, so this drives the class
// directly, which is the only way to exercise docked / freefloating / version.
const path = require('path')
const GBFS = require(path.join(__dirname, '..', '..', 'upstream/gbfs-validator/gbfs.js'))

// gbfs.js console.logs a schema-load failure straight to stdout, which would
// land in the middle of the report. Send anything it prints to stderr so the
// JSON on stdout stays parseable.
console.log = (...args) => process.stderr.write(args.map(String).join(' ') + '\n')

const config = JSON.parse(process.argv[2])

new GBFS(config.url, config.options || {})
  .validation()
  .then((report) => process.stdout.write(JSON.stringify(report)))
  .catch((err) => {
    process.stderr.write(String((err && err.message) || err))
    process.exit(3)
  })
