import { useQuery } from "@tanstack/react-query";
import { View, Text, FlatList, RefreshControl } from "react-native";

import { api } from "@/lib/api";


interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  is_read: boolean;
  created_at: string;
}

export default function NotificationsScreen() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get<Notification[]>("/api/notifications")).data,
  });

  return (
    <FlatList
      data={data ?? []}
      keyExtractor={(n) => n.id}
      refreshControl={<RefreshControl refreshing={isRefetching && !isLoading} onRefresh={refetch} />}
      contentContainerClassName="p-4"
      ListEmptyComponent={
        <Text className="text-center text-slate-500 mt-8">
          {isLoading ? "Đang tải..." : "Chưa có thông báo"}
        </Text>
      }
      renderItem={({ item }) => (
        <View
          className={`border border-slate-200 rounded-md p-3 mb-2 ${
            item.is_read ? "bg-white" : "bg-sky-50"
          }`}
        >
          <View className="flex-row items-center gap-2">
            {!item.is_read && <View className="w-2 h-2 rounded-full bg-sky-500" />}
            <Text className="text-sm font-semibold text-slate-800 flex-1">
              {item.title}
            </Text>
            <Text className="text-[10px] text-slate-400">
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
          {item.body ? (
            <Text className="text-xs text-slate-600 mt-1">{item.body}</Text>
          ) : null}
        </View>
      )}
    />
  );
}
