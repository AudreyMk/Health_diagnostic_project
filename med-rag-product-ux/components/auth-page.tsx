'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Shield, Stethoscope } from 'lucide-react';
import { toast } from 'sonner';

export default function AuthPage() {
  const [isLoading, setIsLoading] = useState(false);
  const { login, register } = useAppStore();

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerFirstName, setRegisterFirstName] = useState('');
  const [registerLastName, setRegisterLastName] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail || !loginPassword) {
      toast.error('Veuillez remplir tous les champs');
      return;
    }
    setIsLoading(true);
    try {
      await login(loginEmail, loginPassword);
      toast.success('Connexion réussie');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur de connexion';
      // Messages d'erreur lisibles pour l'utilisateur
      if (msg.includes('401') || msg.includes('Identifiants')) {
        toast.error('Email ou mot de passe incorrect');
      } else if (msg.includes('réseau') || msg.includes('fetch')) {
        toast.error('Impossible de contacter le serveur. Vérifiez votre connexion.');
      } else {
        toast.error(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerEmail || !registerPassword || !registerFirstName || !registerLastName) {
      toast.error('Veuillez remplir tous les champs');
      return;
    }
    if (registerPassword.length < 6) {
      toast.error('Le mot de passe doit contenir au moins 6 caractères');
      return;
    }
    setIsLoading(true);
    try {
      await register(registerEmail, registerPassword, registerFirstName, registerLastName);
      toast.success('Compte créé avec succès !');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur lors de la création du compte';
      if (msg.includes('400') || msg.toLowerCase().includes('existe')) {
        toast.error('Cet email est déjà utilisé');
      } else {
        toast.error(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-8">
        {/* Logo and Title */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="relative">
              <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center">
                <Stethoscope className="w-8 h-8 text-primary-foreground" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                <Heart className="w-3 h-3 text-white" />
              </div>
            </div>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">MedRAG</h1>
            <p className="text-muted-foreground mt-2">
              Votre assistant de pré-consultation médicale
            </p>
          </div>
        </div>

        {/* Auth Card */}
        <Card className="border-border/50 shadow-lg">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl text-center">Bienvenue</CardTitle>
            <CardDescription className="text-center">
              Connectez-vous ou créez un compte pour commencer
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="login" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-6">
                <TabsTrigger value="login">Connexion</TabsTrigger>
                <TabsTrigger value="register">Créer un compte</TabsTrigger>
              </TabsList>

              {/* ── Connexion ─────────────────────────────────────────────── */}
              <TabsContent value="login">
                <form onSubmit={handleLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="login-email">Email</Label>
                    <Input
                      id="login-email"
                      type="email"
                      placeholder="votre@email.com"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      disabled={isLoading}
                      autoComplete="email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="login-password">Mot de passe</Label>
                    <Input
                      id="login-password"
                      type="password"
                      placeholder="••••••••"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      disabled={isLoading}
                      autoComplete="current-password"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? 'Connexion…' : 'Se connecter'}
                  </Button>
                </form>
              </TabsContent>

              {/* ── Inscription ───────────────────────────────────────────── */}
              <TabsContent value="register">
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="register-firstname">Prénom</Label>
                      <Input
                        id="register-firstname"
                        type="text"
                        placeholder="Jean"
                        value={registerFirstName}
                        onChange={(e) => setRegisterFirstName(e.target.value)}
                        disabled={isLoading}
                        autoComplete="given-name"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="register-lastname">Nom</Label>
                      <Input
                        id="register-lastname"
                        type="text"
                        placeholder="Dupont"
                        value={registerLastName}
                        onChange={(e) => setRegisterLastName(e.target.value)}
                        disabled={isLoading}
                        autoComplete="family-name"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="register-email">Email</Label>
                    <Input
                      id="register-email"
                      type="email"
                      placeholder="votre@email.com"
                      value={registerEmail}
                      onChange={(e) => setRegisterEmail(e.target.value)}
                      disabled={isLoading}
                      autoComplete="email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="register-password">Mot de passe</Label>
                    <Input
                      id="register-password"
                      type="password"
                      placeholder="••••••••"
                      value={registerPassword}
                      onChange={(e) => setRegisterPassword(e.target.value)}
                      disabled={isLoading}
                      autoComplete="new-password"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? 'Création…' : 'Créer mon compte'}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Trust indicators */}
        <div className="flex items-center justify-center gap-6 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Shield className="w-4 h-4" />
            <span>Données sécurisées</span>
          </div>
          <div className="flex items-center gap-1">
            <Heart className="w-4 h-4" />
            <span>Confidentiel</span>
          </div>
        </div>
      </div>
    </div>
  );
}
