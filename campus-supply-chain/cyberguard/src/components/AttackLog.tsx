import React from 'react';
import { AttackEvent } from '../types';
import { Shield, AlertTriangle, ShieldAlert, Clock, MapPin, Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '../utils';

interface AttackLogProps {
  attacks: AttackEvent[];
}

const AttackLog: React.FC<AttackLogProps> = ({ attacks }) => {
  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] border-l border-white/5 overflow-hidden">
      <div className="p-4 border-b border-white/5 flex items-center justify-between bg-black/20">
        <h2 className="text-xs font-mono uppercase tracking-[0.2em] text-white/60 flex items-center gap-2">
          <Clock className="w-3 h-3 text-blue-500" />
          实时威胁监控
        </h2>
        <span className="text-[10px] font-mono text-emerald-500 animate-pulse flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          在线
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
        <AnimatePresence initial={false}>
          {attacks.map((attack) => (
            <motion.div
              key={attack.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className={cn(
                "p-3 rounded-xl border bg-white/5 transition-all hover:bg-white/10 group",
                attack.severity === '致命' ? "border-red-500/30 bg-red-500/5" : 
                attack.severity === '高危' ? "border-amber-500/30 bg-amber-500/5" : "border-white/5"
              )}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  {attack.severity === '致命' ? (
                    <ShieldAlert className="w-4 h-4 text-red-500" />
                  ) : attack.severity === '高危' ? (
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                  ) : (
                    <Shield className="w-4 h-4 text-emerald-500" />
                  )}
                  <span className="text-[11px] font-mono font-bold text-white/90 group-hover:text-white transition-colors">
                    {attack.sourceIp}
                  </span>
                </div>
                <span className={cn(
                  "text-[9px] px-1.5 py-0.5 rounded font-mono uppercase font-bold",
                  attack.severity === '致命' ? "bg-red-500/20 text-red-400" : 
                  attack.severity === '高危' ? "bg-amber-500/20 text-amber-400" : "bg-white/10 text-white/60"
                )}>
                  {attack.severity}
                </span>
              </div>
              
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-[10px] text-white/40">
                  <MapPin className="w-3 h-3" />
                  <span className="truncate">{attack.sourceLocation.country} • {attack.sourceLocation.city}</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] text-white/40">
                  <Activity className="w-3 h-3" />
                  <span className="text-white/70 font-medium">{attack.attackType}</span>
                </div>
              </div>
              
              <div className="mt-3 pt-2 border-t border-white/5 flex justify-between items-center">
                <span className="text-[9px] font-mono text-white/20">
                  {attack.timestamp.toLocaleTimeString()}
                </span>
                <span className={cn(
                  "text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm",
                  attack.status === '已拦截' ? "bg-emerald-500/10 text-emerald-500/80" : "bg-blue-500/10 text-blue-500/80"
                )}>
                  {attack.status}
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default AttackLog;
