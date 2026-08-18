const path = require('path')
const fs = require('fs')
const writeMeta = require('./write_meta')
const crypto = require('crypto')
const root = path.join(__dirname, '..', '..')
const base = path.join(root, 'upstream/gbfs-validator/versions/partials')
const PARAMS = {
  required_vehicle_type_id: {
    vehicleTypes: [
      {
        vehicle_type_id: 'ebike1',
        form_factor: 'bicycle',
        propulsion_type: 'electric_assist'
      },
      {
        vehicle_type_id: 'human1',
        form_factor: 'bicycle',
        propulsion_type: 'human'
      }
    ]
  },
  required_vehicle_types_available: {
    vehicleTypes: [
      {
        vehicle_type_id: 'ebike1',
        form_factor: 'bicycle',
        propulsion_type: 'electric_assist'
      }
    ]
  },
  required_store_uri: { ios: true, android: false },
  pricing_plan_id: { pricingPlans: [{ plan_id: 'p1' }, { plan_id: 'p2' }] },
  default_reserve_time_require: { pricingPlansIdsWithReservationPrice: ['p1'] }
}

const out = {}
for (const version of fs.readdirSync(base).sort()) {
  for (const dir of fs.readdirSync(path.join(base, version)).sort()) {
    for (const f of fs.readdirSync(path.join(base, version, dir)).sort()) {
      const stem = f.replace(/\.js$/, '')
      const gen = require(path.join(base, version, dir, f))
      out[`${version.slice(1)}/${dir}/${stem}`] = gen(PARAMS[stem])
    }
  }
}
fs.writeFileSync(
  path.join(root, 'tests/fixtures/partials/goldens.json'),
  JSON.stringify(out, null, 2)
)

writeMeta()
