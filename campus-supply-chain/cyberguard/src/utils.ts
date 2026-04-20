import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const GEODATA = [
  { country: '美国', cities: [
    { name: '纽约', lat: 40.7128, lng: -74.0060 },
    { name: '洛杉矶', lat: 34.0522, lng: -118.2437 },
    { name: '芝加哥', lat: 41.8781, lng: -87.6298 },
    { name: '华盛顿', lat: 38.9072, lng: -77.0369 },
    { name: '旧金山', lat: 37.7749, lng: -122.4194 }
  ]},
  { country: '俄罗斯', cities: [
    { name: '莫斯科', lat: 55.7558, lng: 37.6173 },
    { name: '圣彼得堡', lat: 59.9343, lng: 30.3351 },
    { name: '新西伯利亚', lat: 55.0084, lng: 82.9357 }
  ]},
  { country: '德国', cities: [
    { name: '柏林', lat: 52.5200, lng: 13.4050 },
    { name: '慕尼黑', lat: 48.1351, lng: 11.5820 },
    { name: '法兰克福', lat: 50.1109, lng: 8.6821 }
  ]},
  { country: '日本', cities: [
    { name: '东京', lat: 35.6762, lng: 139.6503 },
    { name: '大阪', lat: 34.6937, lng: 135.5023 },
    { name: '京都', lat: 35.0116, lng: 135.7681 }
  ]},
  { country: '英国', cities: [
    { name: '伦敦', lat: 51.5074, lng: -0.1278 },
    { name: '曼彻斯特', lat: 53.4808, lng: -2.2426 },
    { name: '爱丁堡', lat: 55.9533, lng: -3.1883 }
  ]},
  { country: '法国', cities: [
    { name: '巴黎', lat: 48.8566, lng: 2.3522 },
    { name: '里昂', lat: 45.7640, lng: 4.8357 },
    { name: '马赛', lat: 43.2965, lng: 5.3698 }
  ]},
  { country: '巴西', cities: [
    { name: '圣保罗', lat: -23.5505, lng: -46.6333 },
    { name: '里约热内卢', lat: -22.9068, lng: -43.1729 },
    { name: '巴西利亚', lat: -15.7975, lng: -47.8919 }
  ]},
  { country: '韩国', cities: [
    { name: '首尔', lat: 37.5665, lng: 126.9780 },
    { name: '釜山', lat: 35.1796, lng: 129.0756 },
    { name: '仁川', lat: 37.4563, lng: 126.7052 }
  ]},
  { country: '加拿大', cities: [
    { name: '多伦多', lat: 43.6532, lng: -79.3832 },
    { name: '温哥华', lat: 49.2827, lng: -123.1207 },
    { name: '蒙特利尔', lat: 45.5017, lng: -73.5673 }
  ]},
  { country: '澳大利亚', cities: [
    { name: '悉尼', lat: -33.8688, lng: 151.2093 },
    { name: '墨尔本', lat: -37.8136, lng: 144.9631 },
    { name: '布里斯班', lat: -27.4698, lng: 153.0251 }
  ]},
  { country: '印度', cities: [
    { name: '孟买', lat: 19.0760, lng: 72.8777 },
    { name: '德里', lat: 28.6139, lng: 77.2090 },
    { name: '班加罗尔', lat: 12.9716, lng: 77.5946 }
  ]},
  { country: '新加坡', cities: [
    { name: '新加坡', lat: 1.3521, lng: 103.8198 }
  ]},
  { country: '荷兰', cities: [
    { name: '阿姆斯特丹', lat: 52.3676, lng: 4.9041 }
  ]}
];

const ATTACK_TYPES: ('DDoS 攻击' | 'SQL 注入' | '暴力破解' | '跨站脚本' | '恶意软件' | '端口扫描')[] = [
  'DDoS 攻击', 'SQL 注入', '暴力破解', '跨站脚本', '恶意软件', '端口扫描'
];

const SEVERITIES: ('低危' | '中危' | '高危' | '致命')[] = [
  '低危', '中危', '高危', '致命'
];

export function generateRandomAttack(targetLat: number, targetLng: number) {
  const countryData = GEODATA[Math.floor(Math.random() * GEODATA.length)];
  const city = countryData.cities[Math.floor(Math.random() * countryData.cities.length)];
  const severity = SEVERITIES[Math.floor(Math.random() * SEVERITIES.length)];
  
  return {
    id: Math.random().toString(36).substr(2, 9),
    timestamp: new Date(),
    sourceIp: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
    sourceLocation: {
      lat: city.lat,
      lng: city.lng,
      city: city.name,
      country: countryData.country,
    },
    targetIp: '202.198.16.1',
    targetLocation: { lat: targetLat, lng: targetLng },
    attackType: ATTACK_TYPES[Math.floor(Math.random() * ATTACK_TYPES.length)],
    severity,
    status: '已拦截' as const,
  };
}
