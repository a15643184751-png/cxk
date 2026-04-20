export interface AttackEvent {
  id: string;
  timestamp: Date;
  sourceIp: string;
  sourceLocation: {
    lat: number;
    lng: number;
    city: string;
    country: string;
  };
  targetIp: string;
  targetLocation: {
    lat: number;
    lng: number;
  };
  attackType: 'DDoS 攻击' | 'SQL 注入' | '暴力破解' | '跨站脚本' | '恶意软件' | '端口扫描';
  severity: '低危' | '中危' | '高危' | '致命';
  status: '已拦截' | '监控中';
}

export interface Stats {
  totalBlocked: number;
  activeThreats: number;
  uptime: string;
  topSourceCountry: string;
}
