import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// One shared client for the whole app. The Supabase SDK handles storing
// the session (in localStorage) and refreshing the access token for us —
// we never manually manage tokens beyond reading the current session.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
