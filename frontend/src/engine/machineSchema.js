// Accepts both compact UI records and MongoDB API fields.
export const normalizeMachine = r => {
  const kw = Number(r.kw ?? r.power ?? r.power_kw ?? 0);
  const units = Number(r.u ?? r.unitsPerHour ?? r.units_per_hour ?? 1);
  const temp = Number(r.temp ?? r.temperature ?? 0);
  return {
    id: r.id ?? r.machineId ?? r.machine_id,
    n: r.n ?? r.machineName ?? r.name,
    ty: r.ty ?? r.machineType ?? r.machine_type ?? 'Other',
    cat: r.cat ?? r.category ?? 'Production',
    loc: r.loc ?? r.location ?? r.plant ?? '-',
    kw,
    kw0: Number(r.kw0 ?? kw),
    rt: Number(r.rt ?? r.ratedPower ?? r.rated_power ?? 0),
    u: units > 0 ? units : 1,
    con: r.con ?? r.operationalConstraint ?? r.operational_constraint,
    pf: Number(r.pf ?? r.powerFactor ?? r.power_factor ?? 1),
    temp,
    bT: Number(r.bT ?? r.baselineTemp ?? r.baseline_temp ?? temp),
    bK: Number(r.bK ?? r.baselineKwhPerUnit ?? r.baseline_kwh_per_unit ?? 0),
    idle: r.idle ?? r.isIdle ?? false,
    voltage: r.voltage,
    current: r.current,
    energy: r.energy,
    status: r.status,
    lastReadingAt: r.lastReadingAt ?? r.last_reading_at,
    mlAssetId: r.mlAssetId ?? r.ml_asset_id,
    maintenance: r.maintenanceStatus,
  };
};
