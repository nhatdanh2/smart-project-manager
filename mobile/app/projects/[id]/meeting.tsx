import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { View, Text, FlatList, ActivityIndicator } from "react-native";

import { api } from "@/lib/api";


interface Meeting {
  id: string;
  title: string | null;
  file_type: string;
  status: string;
  created_at: string;
}

export default function MobileMeeting() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["meetings", id],
    queryFn: async () => (await api.get<Meeting[]>(`/api/projects/${id}/meetings`)).data,
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <View className="flex-1 items-center justify-center">
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <FlatList
      data={data ?? []}
      keyExtractor={(m) => m.id}
      contentContainerClassName="p-4"
      ListEmptyComponent={<Text className="text-center text-slate-500">Chưa có biên bản</Text>}
      renderItem={({ item }) => (
        <View className="bg-white border border-slate-200 rounded-md p-3 mb-2">
          <Text className="text-sm font-medium text-slate-800">
            {item.title || "(không tên)"}
          </Text>
          <View className="flex-row gap-3 mt-1 text-xs text-slate-500">
            <Text>{item.file_type}</Text>
            <Text>{new Date(item.created_at).toLocaleDateString()}</Text>
            <Text
              className={`px-1.5 py-0.5 rounded ${
                item.status === "done"
                  ? "bg-green-100 text-green-700"
                  : "bg-yellow-100 text-yellow-700"
              }`}
            >
              {item.status}
            </Text>
          </View>
        </View>
      )}
    />
  );
}
