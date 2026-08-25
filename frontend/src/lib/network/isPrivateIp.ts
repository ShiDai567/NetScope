/**
 * Private IP 判定（AGENTS.md §23）。
 * 私有 IP 禁止参与公网 GeoIP 定位。
 */
const PRIVATE_RANGES: [number, number][] = [
  [0x0a000000, 0x0affffff], // 10.0.0.0/8
  [0xac100000, 0xac1fffff], // 172.16.0.0/12
  [0xc0a80000, 0xc0a8ffff], // 192.168.0.0/16
  [0x7f000000, 0x7fffffff], // 127.0.0.0/8
  [0xa9fe0000, 0xa9feffff], // 169.254.0.0/16
  [0x64400000, 0x647fffff], // 100.64.0.0/10
];

export function isPrivateIP(ip: string | null | undefined): boolean {
  if (!ip) return false;
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(ip.trim());
  if (!m) return true; // 非法 IP 一律视为不可定位
  const octets = m.slice(1).map(Number);
  if (octets.some((o) => o > 255)) return true;
  const v =
    ((octets[0] as number) << 24) |
    ((octets[1] as number) << 16) |
    ((octets[2] as number) << 8) |
    (octets[3] as number);
  return PRIVATE_RANGES.some(([lo, hi]) => v >>> 0 >= lo && v >>> 0 <= hi);
}
