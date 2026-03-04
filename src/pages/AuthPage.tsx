import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Car, Shield, User } from 'lucide-react';

type Mode = 'login' | 'register';
type Role = 'user' | 'admin';

export default function AuthPage() {
  const navigate = useNavigate();
  const { login, register } = useParkingStore();
  const [mode, setMode] = useState<Mode>('login');
  const [role, setRole] = useState<Role>('user');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'login') {
      const ok = login(email, password, role);
      if (ok) navigate(role === 'admin' ? '/admin' : '/dashboard');
      else setError('Invalid credentials. Use admin@park.com for admin.');
    } else {
      register(name, email, password);
      navigate('/dashboard');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full opacity-10" style={{ background: 'var(--gradient-hero)' }} />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full opacity-10" style={{ background: 'var(--gradient-hero)' }} />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4" style={{ background: 'var(--gradient-hero)' }}>
            <Car className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-display font-bold text-foreground">ParkSmart</h1>
          <p className="text-muted-foreground mt-1">Smart Parking Management System</p>
        </div>

        <div className="bg-card rounded-2xl border border-border p-8 card-shadow">
          {/* Role Toggle */}
          <div className="flex rounded-xl overflow-hidden border border-border mb-6 bg-muted">
            <button
              type="button"
              onClick={() => setRole('user')}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-all ${role === 'user' ? 'bg-primary text-primary-foreground rounded-xl shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <User className="w-4 h-4" /> User
            </button>
            <button
              type="button"
              onClick={() => setRole('admin')}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-all ${role === 'admin' ? 'bg-primary text-primary-foreground rounded-xl shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Shield className="w-4 h-4" /> Admin
            </button>
          </div>

          {/* Mode toggle */}
          {role === 'user' && (
            <div className="flex gap-4 mb-6 border-b border-border pb-4">
              <button
                type="button"
                onClick={() => setMode('login')}
                className={`text-sm font-medium pb-1 border-b-2 transition-colors ${mode === 'login' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => setMode('register')}
                className={`text-sm font-medium pb-1 border-b-2 transition-colors ${mode === 'register' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
              >
                Register
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && role === 'user' && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Full Name</Label>
                <Input id="name" placeholder="John Smith" value={name} onChange={e => setName(e.target.value)} required />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder={role === 'admin' ? 'admin@park.com' : 'you@example.com'} value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
            {error && <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>}
            {role === 'admin' && (
              <p className="text-xs text-muted-foreground bg-muted rounded-lg px-3 py-2">
                Demo: <strong>admin@park.com</strong> / any password
              </p>
            )}
            <Button type="submit" className="w-full h-11 font-semibold" style={{ background: 'var(--gradient-hero)', border: 'none' }}>
              {mode === 'login' ? `Sign In as ${role === 'admin' ? 'Admin' : 'User'}` : 'Create Account'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
