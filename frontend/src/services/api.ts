/**
 * REST API client for JARVIS Holographic UI.
 */

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  content: string;
  role: string;
  model: string;
  provider: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
}

export interface VoiceProfile {
  profile_id: string;
  display_name: string;
  provider: string;
  language: string;
  locale: string;
  gender: string;
  tone: string;
  speed: number;
  description: string;
}

export interface VoicePreferences {
  user_id: string;
  selected_profile_id: string;
  speed: number;
  stability: number;
  voice_enabled: boolean;
  privacy_mode: boolean;
  active_profile?: VoiceProfile;
}

export interface VoiceSynthesisResult {
  audio_base64: string;
  content_type: string;
  character_count: number;
  duration_seconds: number;
  profile_id: string;
  provider: string;
  latency_ms: number;
}

export interface PendingApproval {
  id: string;
  tool_name: string;
  tool_version: string;
  risk_class: string;
  action_summary: string;
  arguments_hash: string;
  status: string;
  created_at: string;
  expires_at: string;
}

export interface ModelUsage {
  total_calls: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  avg_latency_ms: number;
}

class JarvisAPIClient {
  private token: string | null = null;
  private readonly baseUrl = '/api/v1';

  constructor() {
    this.token = localStorage.getItem('jarvis_auth_token');
  }

  public setToken(token: string) {
    this.token = token;
    localStorage.setItem('jarvis_auth_token', token);
  }

  public getToken(): string | null {
    return this.token;
  }

  /**
   * Automatically ensure an authenticated session for seamless out-of-the-box UX.
   */
  public async ensureAuthenticated(): Promise<string> {
    if (this.token) return this.token;

    const email = 'commander@jarvis.ai';
    const password = 'HolographicPassword123!';

    // Try logging in
    try {
      const loginResp = await fetch(`${this.baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (loginResp.ok) {
        const data = await loginResp.json();
        this.setToken(data.access_token);
        return data.access_token;
      }
    } catch {
      // Ignore login error, try registering
    }

    // Register user if not exists
    try {
      const regResp = await fetch(`${this.baseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          display_name: 'Tony Stark',
          timezone: 'Asia/Kolkata',
        }),
      });

      if (regResp.ok) {
        const data = await regResp.json();
        this.setToken(data.access_token);
        return data.access_token;
      }
    } catch (err) {
      console.warn('Could not auto-register demo user:', err);
    }

    return '';
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    let token = await this.ensureAuthenticated();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let res = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    // If 401 Unauthorized, token may be expired or invalid in localStorage: clear and retry once
    if (res.status === 401) {
      this.token = null;
      localStorage.removeItem('jarvis_auth_token');
      token = await this.ensureAuthenticated();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        res = await fetch(`${this.baseUrl}${endpoint}`, {
          ...options,
          headers,
        });
      }
    }

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API ${res.status}: ${errorText || res.statusText}`);
    }

    return res.json() as Promise<T>;
  }

  // Models
  public async sendChat(messages: LLMMessage[], role?: string): Promise<ChatResponse> {
    const payload: { messages: LLMMessage[]; role?: string } = { messages };
    if (role && role !== 'auto') {
      payload.role = role;
    }
    return this.request<ChatResponse>('/models/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  public async getModelRoutes(): Promise<any> {
    return this.request<any>('/models/routes');
  }

  public async getModelUsage(): Promise<ModelUsage> {
    return this.request<ModelUsage>('/models/usage');
  }

  // Voice
  public async getVoiceProfiles(): Promise<VoiceProfile[]> {
    return this.request<VoiceProfile[]>('/voice/profiles');
  }

  public async getVoicePreferences(): Promise<VoicePreferences> {
    return this.request<VoicePreferences>('/voice/preferences');
  }

  public async updateVoicePreferences(update: Partial<VoicePreferences>): Promise<VoicePreferences> {
    return this.request<VoicePreferences>('/voice/preferences', {
      method: 'PUT',
      body: JSON.stringify(update),
    });
  }

  public async synthesizeSpeech(text: string, profile_id?: string): Promise<VoiceSynthesisResult> {
    return this.request<VoiceSynthesisResult>('/voice/synthesize', {
      method: 'POST',
      body: JSON.stringify({ text, profile_id, format: 'mp3' }),
    });
  }

  // Approvals
  public async getPendingApprovals(): Promise<PendingApproval[]> {
    return this.request<PendingApproval[]>('/approvals/pending');
  }

  public async decideApproval(id: string, decision: 'APPROVE' | 'REJECT', reason?: string): Promise<any> {
    return this.request<any>(`/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    });
  }

  // System Telemetry & Desktop Automation
  public async getSystemStatus(): Promise<SystemStatus> {
    return this.request<SystemStatus>('/system/status');
  }

  public async executeSystemAction(action: string, param?: string): Promise<{ success: boolean; action: string; result: any }> {
    return this.request('/system/action', {
      method: 'POST',
      body: JSON.stringify({ action, param }),
    });
  }

  public async getLiveTelemetry(): Promise<any> {
    return this.request('/system/telemetry');
  }

  public async inspectScreenImage(image_base64: string, prompt?: string): Promise<{ success: boolean; analysis: string }> {
    return this.request('/system/screen/inspect', {
      method: 'POST',
      body: JSON.stringify({ image_base64, prompt }),
    });
  }

  public async updateSystemKeys(keys: {
    elevenlabs_api_key?: string;
    nvidia_api_key?: string;
    grok_api_key?: string;
    groq_api_key?: string;
    openai_api_key?: string;
  }): Promise<{ success: boolean; message: string; elevenlabs_valid?: boolean; ai_valid?: boolean; status: SystemStatus }> {
    return this.request('/system/keys', {
      method: 'POST',
      body: JSON.stringify(keys),
    });
  }
}

export interface SystemStatus {
  status: string;
  ai_provider: string;
  ai_configured: boolean;
  voice_provider: string;
  voice_configured: boolean;
  elevenlabs_configured: boolean;
  nvidia_configured: boolean;
  groq_configured: boolean;
  grok_configured: boolean;
  openai_configured: boolean;
  active_profile_id: string;
}

export const api = new JarvisAPIClient();
