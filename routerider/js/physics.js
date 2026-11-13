// Virtual-speed model: turns rider power + road grade into forward speed.
const G = 9.81;
const RHO = 1.225;
const DRIVETRAIN = 0.97;

export function stepSpeed(v, power, grade, dt, cfg) {
  const m = cfg.riderKg + cfg.bikeKg;
  const theta = Math.atan(grade);
  const gravity = m * G * Math.sin(theta);
  const rolling = v > 0.01 ? cfg.crr * m * G * Math.cos(theta) : 0;
  const aero = 0.5 * RHO * cfg.cda * v * v;
  const drive = (power * DRIVETRAIN) / Math.max(v, 1);
  const a = (drive - gravity - rolling - aero) / (m * 1.05); // +5 % for rotating mass
  return Math.max(0, v + a * dt);
}

// Steady-state speed for a given power & grade (used for estimates).
export function steadySpeed(power, grade, cfg) {
  let v = 5;
  for (let i = 0; i < 400; i++) v = stepSpeed(v, power, grade, 0.5, cfg);
  return v;
}
