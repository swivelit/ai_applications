import React, { useState } from "react";
import {
  SafeAreaView,
  Text,
  TextInput,
  View,
  Pressable,
  Alert,
  ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { getProfile, submitQuestionnaire, generateDailyCheckins } from "@/lib/account";
import { ensureNotificationsReady, scheduleReminder, cancelAllReminders } from "@/lib/reminders";

export default function Questionnaire() {
  const [workStart, setWorkStart] = useState("09:30");
  const [workEnd, setWorkEnd] = useState("18:30");
  const [sleep, setSleep] = useState("23:30");
  const [wake, setWake] = useState("07:30");
  const [dailyHabits, setDailyHabits] = useState("Water, Focus work, Walk");
  const [busy, setBusy] = useState(false);

  function validateHHMM(v: string) {
    return /^([01]\d|2[0-3]):([0-5]\d)$/.test(v.trim());
  }

  async function finish() {
    if (busy) return;

    if (![workStart, workEnd, sleep, wake].every(validateHHMM)) {
      Alert.alert("Invalid time", "Please use HH:MM format, for example 07:30.");
      return;
    }

    try {
      setBusy(true);

      const profile = await getProfile();
      if (!profile?.userId) {
        Alert.alert("Profile missing", "Please create your profile again.");
        return;
      }

      await submitQuestionnaire(profile.userId, {
        workStart,
        workEnd,
        sleep,
        wake,
        dailyHabits,
      });

      const notificationsReady = await ensureNotificationsReady();
      if (!notificationsReady) {
        Alert.alert(
          "Notifications disabled",
          "Enable notifications to receive smart check-ins. You can still use the app."
        );
        router.replace("/(tabs)");
        return;
      }

      await cancelAllReminders();

      try {
        const out = await generateDailyCheckins(profile.userId);
        let scheduledCount = 0;
        const now = Date.now();

        for (const c of out.checkins || []) {
          try {
            if (!c?.when || !validateHHMM(c.when)) continue;

            const [hh, mm] = c.when.split(":").map(Number);
            const when = new Date();
            when.setHours(hh, mm, 0, 0);

            if (when.getTime() <= now + 30_000) {
              when.setDate(when.getDate() + 1);
            }

            await scheduleReminder(c.title, c.message, when);
            scheduledCount += 1;
          } catch (err) {
            console.warn("Failed to schedule check-in", c, err);
          }
        }

        Alert.alert("All set ✅", `Scheduled ${scheduledCount} check-ins.`);
      } catch {
        Alert.alert("Saved ✅", "Routine saved. Check-ins can be generated later.");
      }

      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Failed to finish onboarding");
    } finally {
      setBusy(false);
    }
  }

  return (
    <LinearGradient colors={["#070A14", "#0B1020", "#121A33"]} style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1, padding: 18 }}>
        <Text style={{ color: "white", fontSize: 26, fontWeight: "900" }}>
          Daily routine
        </Text>
        <Text style={{ color: "rgba(255,255,255,0.65)", marginTop: 8 }}>
          This is used for reminders, check-ins, and better responses.
        </Text>

        <Row label="Work start (HH:MM)" value={workStart} setValue={setWorkStart} />
        <Row label="Work end (HH:MM)" value={workEnd} setValue={setWorkEnd} />
        <Row label="Wake time" value={wake} setValue={setWake} />
        <Row label="Sleep time" value={sleep} setValue={setSleep} />
        <Row label="Daily habits" value={dailyHabits} setValue={setDailyHabits} />

        <Pressable onPress={finish} style={[btn, busy && { opacity: 0.6 }]} disabled={busy}>
          {busy ? (
            <ActivityIndicator />
          ) : (
            <Text style={{ color: "white", fontWeight: "900" }}>
              Finish & Continue
            </Text>
          )}
        </Pressable>
      </SafeAreaView>
    </LinearGradient>
  );
}

function Row({ label, value, setValue }: any) {
  return (
    <View style={{ marginTop: 14 }}>
      <Text style={{ color: "rgba(255,255,255,0.75)", fontWeight: "800" }}>
        {label}
      </Text>
      <TextInput
        value={value}
        onChangeText={setValue}
        placeholder="HH:MM"
        placeholderTextColor="rgba(255,255,255,0.35)"
        style={input}
      />
    </View>
  );
}

const input = {
  marginTop: 8,
  height: 52,
  borderRadius: 16,
  paddingHorizontal: 14,
  color: "white",
  backgroundColor: "rgba(255,255,255,0.08)",
  borderWidth: 1,
  borderColor: "rgba(255,255,255,0.12)",
};

const btn = {
  marginTop: 18,
  height: 54,
  borderRadius: 16,
  alignItems: "center" as const,
  justifyContent: "center" as const,
  backgroundColor: "rgba(34,211,238,0.22)",
  borderWidth: 1,
  borderColor: "rgba(34,211,238,0.35)",
};