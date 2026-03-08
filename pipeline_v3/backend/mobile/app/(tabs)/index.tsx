import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  Text,
  TextInput,
  View,
  Pressable,
  ScrollView,
  Alert,
  Modal,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Audio } from "expo-av";
import * as Haptics from "expo-haptics";

import { GlassCard } from "@/components/Glass";
import { Waveform } from "@/components/Waveform";
import { useAssistant } from "@/components/AssistantProvider";
import { apiPost, apiPostForm } from "@/lib/api";
import { getProfile } from "@/lib/account";
import { parseDatetime } from "@/lib/datetime";
import { scheduleReminder } from "@/lib/reminders";
import { ChatResponse } from "@/lib/types";

export default function Home() {
  const { name, settings } = useAssistant();

  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [listening, setListening] = useState(false);

  const [result, setResult] = useState<ChatResponse | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingReminder, setPendingReminder] = useState<{
    title: string;
    details: string;
    datetimeText: string;
  } | null>(null);

  const placeholder = useMemo(() => {
    return settings.languageMode === "ta"
      ? "தமிழில் சொல்லுங்க…"
      : "Tamil / Tanglish…";
  }, [settings.languageMode]);

  function stripAssistantTrigger(input: string) {
    const cleaned = input.trim();
    if (!cleaned) return cleaned;

    const trigger = (name || "Ellie").trim().toLowerCase();
    const lower = cleaned.toLowerCase();

    if (lower.startsWith(trigger)) {
      let rest = cleaned.slice((name || "Ellie").length).trim();
      rest = rest.replace(/^[:,\-–—]+/, "").trim();
      return rest || cleaned;
    }
    return cleaned;
  }

  function maybeExtractReminderTime(message: string, aiText: string) {
    const source = `${message} ${aiText}`.toLowerCase();
    const reminderWords = ["remind", "reminder", "schedule", "meeting", "birthday", "tomorrow", "today"];
    const matched = reminderWords.some((w) => source.includes(w));
    return matched ? message : null;
  }

  async function analyzeText() {
    if (!text.trim()) return;

    try {
      setBusy(true);

      const profile = await getProfile();
      if (!profile?.userId) {
        Alert.alert("Profile missing", "Please complete onboarding first.");
        return;
      }

      const cleaned = stripAssistantTrigger(text);

      const res = await apiPost<ChatResponse>("/api/chat", {
        user_id: profile.userId,
        message: cleaned,
      });

      setResult(res);
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);

      const maybeTime = maybeExtractReminderTime(
        cleaned,
        res.result?.theni_tamil_text || res.result?.tamil_text || ""
      );

      if (maybeTime) {
        setPendingReminder({
          title: "Reminder",
          details: cleaned,
          datetimeText: maybeTime,
        });
        setConfirmOpen(true);
      }
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    try {
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      setListening(true);

      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) {
        setListening(false);
        Alert.alert("Mic permission needed", "Please allow microphone access.");
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const rec = new Audio.Recording();
      await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await rec.startAsync();
      setRecording(rec);
    } catch (e: any) {
      setListening(false);
      Alert.alert("Error", e?.message || "Could not start recording");
    }
  }

  async function stopAndAnalyze() {
    if (!recording) return;

    try {
      setBusy(true);
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      setListening(false);

      if (!uri) throw new Error("No audio file URI");

      const profile = await getProfile();
      if (!profile?.userId) {
        Alert.alert("Profile missing", "Please complete onboarding first.");
        return;
      }

      const form = new FormData();
      form.append("file", {
        uri,
        name: "audio.m4a",
        type: "audio/m4a",
      } as any);

      const res = await apiPostForm<ChatResponse>(
        `/transcribe-and-analyze?user_id=${encodeURIComponent(profile.userId)}`,
        form
      );

      setResult(res);
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Voice analyze failed");
    } finally {
      setBusy(false);
    }
  }

  function chip(t: string) {
    setText(t);
  }

  async function confirmScheduleReminder() {
    if (!pendingReminder) return;

    try {
      setBusy(true);

      const profile = await getProfile();
      const tz = profile?.timezone || "Asia/Kolkata";

      const parsed = await parseDatetime(pendingReminder.datetimeText, tz);

      if (!parsed.iso || parsed.confidence < 0.35) {
        Alert.alert(
          "Confirm time",
          `I couldn’t confidently understand the reminder time.\n\nDetected text:\n"${pendingReminder.datetimeText}"`
        );
        setConfirmOpen(false);
        setPendingReminder(null);
        return;
      }

      const when = new Date(parsed.iso);
      if (isNaN(when.getTime())) {
        Alert.alert("Error", "Parsed datetime was invalid.");
        setConfirmOpen(false);
        setPendingReminder(null);
        return;
      }

      if (when.getTime() < Date.now() + 30_000) {
        Alert.alert("Time is too soon", "Please choose a future time.");
        setConfirmOpen(false);
        setPendingReminder(null);
        return;
      }

      await scheduleReminder(
        pendingReminder.title,
        pendingReminder.details,
        when
      );

      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert("Reminder set ✅", parsed.human || when.toString());
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Failed to schedule reminder");
    } finally {
      setBusy(false);
      setConfirmOpen(false);
      setPendingReminder(null);
    }
  }

  return (
    <LinearGradient colors={["#070A14", "#0B1020", "#121A33"]} style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1, paddingHorizontal: 16, paddingTop: 10 }}>
        <ScrollView contentContainerStyle={{ paddingBottom: 140 }}>
          <Text style={{ color: "rgba(255,255,255,0.92)", fontSize: 28, fontWeight: "900" }}>
            Persona Tamil AI
          </Text>
          <Text style={{ marginTop: 8, color: "rgba(255,255,255,0.60)", fontSize: 14 }}>
            Hi, I am {name}. Ask in Tamil, Tanglish, or English.
          </Text>

          <GlassCard style={{ marginTop: 16 }}>
            <TextInput
              value={text}
              onChangeText={setText}
              multiline
              placeholder={placeholder}
              placeholderTextColor="rgba(255,255,255,0.35)"
              style={{
                minHeight: 110,
                color: "white",
                fontSize: 16,
                lineHeight: 22,
              }}
            />

            <Pressable
              onPress={analyzeText}
              disabled={busy}
              style={{
                marginTop: 12,
                height: 52,
                borderRadius: 16,
                backgroundColor: "rgba(34,211,238,0.22)",
                borderWidth: 1,
                borderColor: "rgba(34,211,238,0.35)",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ color: "white", fontWeight: "900", fontSize: 16 }}>
                {busy ? "WORKING…" : "SEND"}
              </Text>
            </Pressable>

            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
              {[
                "Ellie, நாளைக்கு காலை 8 மணிக்கு office meeting reminder வை",
                "எனக்கு healthy breakfast idea சொல்லு",
                "Today customer followup task add pannunga",
                "Amma ku medicine reminder vechiko",
              ].map((c) => (
                <Pressable
                  key={c}
                  onPress={() => chip(c)}
                  style={{
                    paddingHorizontal: 12,
                    paddingVertical: 8,
                    borderRadius: 999,
                    borderWidth: 1,
                    borderColor: "rgba(255,255,255,0.10)",
                    backgroundColor: "rgba(255,255,255,0.06)",
                  }}
                >
                  <Text style={{ color: "rgba(255,255,255,0.75)", fontWeight: "700" }}>{c}</Text>
                </Pressable>
              ))}
            </View>
          </GlassCard>

          <View style={{ marginTop: 18 }}>
            <Text style={{ color: "rgba(255,255,255,0.78)", fontWeight: "900", fontSize: 16 }}>
              Voice (Tamil)
            </Text>
            <Text style={{ marginTop: 6, color: "rgba(255,255,255,0.55)" }}>
              Tap below to {recording ? "stop & analyze" : "start recording"}.
            </Text>

            <GlassCard style={{ marginTop: 12, alignItems: "center" }}>
              <Waveform active={!!recording} />
              <Pressable
                onPress={recording ? stopAndAnalyze : startRecording}
                style={{
                  marginTop: 14,
                  paddingHorizontal: 18,
                  paddingVertical: 10,
                  borderRadius: 999,
                  backgroundColor: listening
                    ? "rgba(239,68,68,0.30)"
                    : "rgba(34,211,238,0.22)",
                  borderWidth: 1,
                  borderColor: listening
                    ? "rgba(239,68,68,0.45)"
                    : "rgba(34,211,238,0.35)",
                }}
              >
                <Text style={{ color: "white", fontWeight: "900" }}>
                  {recording ? "STOP & ANALYZE" : "START RECORDING"}
                </Text>
              </Pressable>
            </GlassCard>
          </View>

          {result && (
            <GlassCard style={{ marginTop: 16 }}>
              <Text style={{ color: "rgba(255,255,255,0.92)", fontSize: 18, fontWeight: "900" }}>
                AI Response
              </Text>

              <Text style={{ marginTop: 12, color: "rgba(255,255,255,0.92)", fontSize: 16 }}>
                {result.result?.theni_tamil_text || result.result?.tamil_text || "No response"}
              </Text>

              {!!result.result?.remodeled_english && (
                <Text style={{ marginTop: 10, color: "rgba(255,255,255,0.62)" }}>
                  English: {result.result.remodeled_english}
                </Text>
              )}

              <View style={{ marginTop: 12, gap: 6 }}>
                <Text style={{ color: "rgba(255,255,255,0.70)" }}>
                  Route: {result.result?.route_taken || "-"}
                </Text>
                <Text style={{ color: "rgba(255,255,255,0.70)" }}>
                  Risk: {result.result?.risk_level || "-"}
                </Text>
                <Text style={{ color: "rgba(255,255,255,0.70)" }}>
                  Label: {result.result?.predicted_label || "-"}
                </Text>
              </View>
            </GlassCard>
          )}
        </ScrollView>

        <Modal visible={confirmOpen} transparent animationType="fade">
          <View
            style={{
              flex: 1,
              backgroundColor: "rgba(0,0,0,0.6)",
              justifyContent: "center",
              padding: 20,
            }}
          >
            <View
              style={{
                borderRadius: 20,
                padding: 18,
                backgroundColor: "#111827",
                borderWidth: 1,
                borderColor: "rgba(255,255,255,0.10)",
              }}
            >
              <Text style={{ color: "white", fontSize: 18, fontWeight: "900" }}>
                Schedule reminder?
              </Text>
              <Text style={{ color: "rgba(255,255,255,0.72)", marginTop: 10 }}>
                I detected a reminder-like request from your message.
              </Text>
              <Text style={{ color: "rgba(255,255,255,0.92)", marginTop: 12 }}>
                {pendingReminder?.datetimeText}
              </Text>

              <View style={{ flexDirection: "row", gap: 10, marginTop: 18 }}>
                <Pressable
                  onPress={() => {
                    setConfirmOpen(false);
                    setPendingReminder(null);
                  }}
                  style={{
                    flex: 1,
                    height: 48,
                    borderRadius: 14,
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: "rgba(255,255,255,0.08)",
                  }}
                >
                  <Text style={{ color: "white", fontWeight: "800" }}>Cancel</Text>
                </Pressable>

                <Pressable
                  onPress={confirmScheduleReminder}
                  style={{
                    flex: 1,
                    height: 48,
                    borderRadius: 14,
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: "rgba(34,211,238,0.22)",
                    borderWidth: 1,
                    borderColor: "rgba(34,211,238,0.35)",
                  }}
                >
                  <Text style={{ color: "white", fontWeight: "900" }}>Confirm</Text>
                </Pressable>
              </View>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </LinearGradient>
  );
}