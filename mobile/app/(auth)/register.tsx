import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert, ScrollView } from "react-native";
import { Link } from "expo-router";

import { useAuth } from "@/providers/AuthProvider";


export default function RegisterScreen() {
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (password.length < 8) {
      Alert.alert("Mật khẩu quá ngắn", "Tối thiểu 8 ký tự");
      return;
    }
    setBusy(true);
    try {
      await register(email.trim(), name.trim(), password);
    } catch (err: any) {
      Alert.alert("Đăng ký thất bại", err?.response?.data?.detail || "Vui lòng thử lại");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerClassName="p-6">
      <Text className="text-2xl font-bold text-slate-800 mb-1">Tạo tài khoản</Text>
      <Text className="text-sm text-slate-500 mb-6">Miễn phí cho sinh viên & giảng viên</Text>

      <View className="space-y-3">
        <View>
          <Text className="text-xs text-slate-600 mb-1">Họ tên</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            className="border border-slate-300 rounded-md px-3 py-2"
            placeholder="Nguyễn Văn A"
          />
        </View>
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
          <Text className="text-xs text-slate-600 mb-1">Mật khẩu (≥8 ký tự)</Text>
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
            {busy ? "Đang tạo..." : "Tạo tài khoản"}
          </Text>
        </TouchableOpacity>
      </View>

      <View className="mt-6 flex-row justify-center">
        <Text className="text-sm text-slate-500">Đã có tài khoản? </Text>
        <Link href="/login" className="text-sky-600 font-medium">
          Đăng nhập
        </Link>
      </View>
    </ScrollView>
  );
}
