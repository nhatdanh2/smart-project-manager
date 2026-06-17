import { TouchableOpacity, Text } from "react-native";


interface Props {
  onPress: () => void;
}

export function LocalAuthButton({ onPress }: Props) {
  return (
    <TouchableOpacity
      onPress={onPress}
      className="border border-sky-500 rounded-md py-3"
    >
      <Text className="text-center text-sky-600 font-medium">🔐 Đăng nhập nhanh</Text>
    </TouchableOpacity>
  );
}
