import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert, ScrollView } from "react-native";
import { Link } from "expo-router";

import { useAuth } from "@/providers/AuthProvider";
import { LocalAuthButton } from "@/components/LocalAuthButton";


export default function LoginScreen() {
  const { login, loginWithBiometric, biometricEnabled } = useAuth();
  const [email, setEmail] = useState("leader@example.com");
  const [password, setPassword] = useState("password123");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await login(email.trim(), password);
    } catch (err: any) {
      Alert.alert("Đăng nhập thất bại", err?.response?.data?.detail || "Vui lòng thử lại");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerClassName="p-6">
      <Text className="text-2xl font-bold text-slate-800 mb-1">Smart PM</Text>
      <Text className="text-sm text-slate-500 mb-6">Quản lý đồ án thông minh</Text>

      <View className="space-y-3">
        <View>
          <Text className="text-xs text-slate-600 mb-1">Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            className="border border-slate-300 rounded-md px-3 py-2"
            placeholder="you@example.com"
          />
        </View>
        <View>
          <Text className="text-xs text-slate-600 mb-1">Mật khẩu</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            className="border border-slate-300 rounded-md px-3 py-2"
            placeholder="••••••••"
          />
        </View>
        <TouchableOpacity
          onPress={submit}
          disabled={busy}
          className={`bg-sky-500 rounded-md py-3 ${busy ? "opacity-50" : ""}`}
        >
          <Text className="text-white text-center font-medium">
            {busy ? "Đang đăng nhập..." : "Đăng nhập"}
          </Text>
        </TouchableOpacity>
      </View>

      {biometricEnabled && (
        <View className="mt-4">
          <LocalAuthButton onPress={loginWithBiometric} />
        </View>
      )}

      <View className="mt-6 flex-row justify-center">
        <Text className="text-sm text-slate-500">Chưa có tài khoản? </Text>
        <Link href="/register" className="text-sky-600 font-medium">
          Đăng ký
        </Link>
      </View>
    </ScrollView>
  );
}
