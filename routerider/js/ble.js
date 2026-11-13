// Bluetooth LE: smart trainers (FTMS / Cycling Power) and heart-rate straps.
// Uses the Web Bluetooth API (Chrome / Edge / Opera on desktop & Android, Bluefy on iOS).

const FTMS = 0x1826;
const FTMS_BIKE_DATA = 0x2ad2;
const FTMS_CONTROL = 0x2ad9;
const CPS = 0x1818;
const CPS_MEASUREMENT = 0x2a63;
const HRS = 0x180d;
const HR_MEASUREMENT = 0x2a37;

export const bleSupported = () => !!navigator.bluetooth;

// Serialise GATT writes – trainers reject overlapping operations ("GATT operation already in progress").
class WriteQueue {
  constructor() { this.p = Promise.resolve(); }
  push(fn) { this.p = this.p.then(fn).catch((e) => console.warn('BLE write failed', e)); return this.p; }
}

export class Trainer extends EventTarget {
  constructor() {
    super();
    this.device = null;
    this.control = null;
    this.queue = new WriteQueue();
    this.lastCrank = null;
    this.mode = null; // 'ftms' | 'cps'
  }

  get connected() { return !!this.device?.gatt?.connected; }
  get canControl() { return !!this.control; }

  async connect() {
    this.device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [FTMS] }, { services: [CPS] }],
      optionalServices: [FTMS, CPS, HRS],
    });
    this.device.addEventListener('gattserverdisconnected', () => this.emit('status', { connected: false }));
    const server = await this.device.gatt.connect();

    try {
      const svc = await server.getPrimaryService(FTMS);
      const data = await svc.getCharacteristic(FTMS_BIKE_DATA);
      data.addEventListener('characteristicvaluechanged', (e) => this.emit('data', parseIndoorBikeData(e.target.value)));
      await data.startNotifications();
      try {
        this.control = await svc.getCharacteristic(FTMS_CONTROL);
        this.control.addEventListener('characteristicvaluechanged', () => {});
        await this.control.startNotifications(); // indications are required before writing
        await this.write([0x00]); // request control
        await this.write([0x07]); // start / resume
      } catch (e) { console.warn('FTMS control point unavailable', e); this.control = null; }
      this.mode = 'ftms';
    } catch {
      const svc = await server.getPrimaryService(CPS);
      const ch = await svc.getCharacteristic(CPS_MEASUREMENT);
      ch.addEventListener('characteristicvaluechanged', (e) => this.emit('data', this.parseCps(e.target.value)));
      await ch.startNotifications();
      this.mode = 'cps';
    }
    this.emit('status', { connected: true, name: this.device.name, control: this.canControl });
  }

  disconnect() { this.device?.gatt?.disconnect(); }

  write(bytes) {
    if (!this.control) return Promise.resolve();
    return this.queue.push(() => this.control.writeValueWithResponse(new Uint8Array(bytes)));
  }

  // Simulation mode: trainer computes resistance from grade, rolling resistance and wind.
  setSimulation(gradePct, crr = 0.004, cw = 0.51) {
    const g = Math.round(Math.max(-40, Math.min(40, gradePct)) * 100); // 0.01 %
    const buf = new DataView(new ArrayBuffer(7));
    buf.setUint8(0, 0x11);
    buf.setInt16(1, 0, true); // wind speed 0.001 m/s
    buf.setInt16(3, g, true);
    buf.setUint8(5, Math.round(crr * 10000));
    buf.setUint8(6, Math.round(cw * 100));
    return this.write(new Uint8Array(buf.buffer));
  }

  // ERG mode: trainer holds a target power regardless of cadence.
  setTargetPower(watts) {
    const buf = new DataView(new ArrayBuffer(3));
    buf.setUint8(0, 0x05);
    buf.setInt16(1, Math.round(watts), true);
    return this.write(new Uint8Array(buf.buffer));
  }

  parseCps(dv) {
    const flags = dv.getUint16(0, true);
    let o = 2;
    const out = { power: dv.getInt16(o, true) };
    o += 2;
    if (flags & 0x01) o += 1; // pedal power balance
    if (flags & 0x04) o += 2; // accumulated torque
    if (flags & 0x10) o += 6; // wheel revolutions
    if (flags & 0x20) {
      const revs = dv.getUint16(o, true), time = dv.getUint16(o + 2, true);
      if (this.lastCrank) {
        const dr = (revs - this.lastCrank.revs + 65536) % 65536;
        const dt = ((time - this.lastCrank.time + 65536) % 65536) / 1024;
        if (dt > 0) this.cadence = Math.round((dr / dt) * 60);
        else if (performance.now() - this.lastCrank.at > 2500) this.cadence = 0;
      }
      if (!this.lastCrank || revs !== this.lastCrank.revs) this.lastCrank = { revs, time, at: performance.now() };
      out.cadence = this.cadence ?? 0;
    }
    return out;
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}

export function parseIndoorBikeData(dv) {
  const flags = dv.getUint16(0, true);
  let o = 2;
  const out = {};
  if (!(flags & 0x0001)) { out.speedKmh = dv.getUint16(o, true) / 100; o += 2; }
  if (flags & 0x0002) o += 2; // average speed
  if (flags & 0x0004) { out.cadence = dv.getUint16(o, true) / 2; o += 2; }
  if (flags & 0x0008) o += 2; // average cadence
  if (flags & 0x0010) o += 3; // total distance
  if (flags & 0x0020) o += 2; // resistance level
  if (flags & 0x0040) { out.power = dv.getInt16(o, true); o += 2; }
  if (flags & 0x0080) o += 2; // average power
  if (flags & 0x0100) o += 5; // energy
  if (flags & 0x0200) { out.hr = dv.getUint8(o); o += 1; }
  return out;
}

export class HeartRate extends EventTarget {
  get connected() { return !!this.device?.gatt?.connected; }
  async connect() {
    this.device = await navigator.bluetooth.requestDevice({ filters: [{ services: [HRS] }] });
    this.device.addEventListener('gattserverdisconnected', () => this.dispatchEvent(new CustomEvent('status', { detail: { connected: false } })));
    const svc = await (await this.device.gatt.connect()).getPrimaryService(HRS);
    const ch = await svc.getCharacteristic(HR_MEASUREMENT);
    ch.addEventListener('characteristicvaluechanged', (e) => {
      const dv = e.target.value;
      const hr = dv.getUint8(0) & 1 ? dv.getUint16(1, true) : dv.getUint8(1);
      this.dispatchEvent(new CustomEvent('data', { detail: { hr } }));
    });
    await ch.startNotifications();
    this.dispatchEvent(new CustomEvent('status', { detail: { connected: true, name: this.device.name } }));
  }
  disconnect() { this.device?.gatt?.disconnect(); }
}
