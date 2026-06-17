import { View, Text, TouchableOpacity, Alert } from "react-native";

import { useAuth } from "@/providers/AuthProvider";


export default function ProfileScreen() {
  const { user, logout, enableBiometric, biometricEnabled } = useAuth();

  return (
    <View className="p-6">
      {user ? (
        <View>
          <Text className="text-xl font-bold text-slate-800">{user.name}</Text>
          <Text className="text-sm text-slate-500">{user.email}</Text>
          <Text className="text-xs text-sky-600 mt-1 capitalize">{user.role}</Text>
        </View>
      ) : null}

      {!biometricEnabled && (
        <TouchableOpacity
          className="mt-6 bg-slate-100 rounded-md py-3"
          onPress={async () => {
            try {
              await enableBiometric();
              Alert.alert("Đã bật", "Lần sau có thể đăng nhập bằng vân tay/Face ID");
            } catch {
              Alert.alert("Không hỗ trợ", "Thiết bị chưa cài sinh trắc học");
            }
          }}
        >
          <Text className="text-center text-slate-700">🔐 Bật đăng nhập sinh trắc học</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        className="mt-3 bg-red-100 rounded-md py-3"
        onPress={logout}
      >
        <Text className="text-center text-red-700">Đăng xuất</Text>
      </TouchableOpacity>
    </View>
  );
}
