import { useQuery } from "@tanstack/react-query";
import { Link } from "expo-router";
import { View, Text, FlatList, RefreshControl, TouchableOpacity } from "react-native";

import { api } from "@/lib/api";


interface Project {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  deadline: string;
}

export default function ProjectsScreen() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get<Project[]>("/api/projects")).data,
  });

  return (
    <FlatList
      data={data ?? []}
      keyExtractor={(p) => p.id}
      refreshControl={
        <RefreshControl refreshing={isRefetching && !isLoading} onRefresh={refetch} />
      }
      contentContainerClassName="p-4"
      ListEmptyComponent={
        <Text className="text-center text-slate-500 mt-8">
          {isLoading ? "Đang tải..." : "Chưa có dự án nào"}
        </Text>
      }
      renderItem={({ item }) => (
        <Link href={`/projects/${item.id}/kanban`} asChild>
          <TouchableOpacity className="bg-white border border-slate-200 rounded-lg p-3 mb-2">
            <Text className="font-semibold text-slate-800">{item.title}</Text>
            {item.description ? (
              <Text className="text-xs text-slate-500 mt-1" numberOfLines={2}>
                {item.description}
              </Text>
            ) : null}
            <View className="flex-row justify-between mt-2 text-xs text-slate-500">
              <Text>📅 {new Date(item.deadline).toLocaleDateString()}</Text>
              <Text className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-700">
                {item.status}
              </Text>
            </View>
          </TouchableOpacity>
        </Link>
      )}
    />
  );
}
