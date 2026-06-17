import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";

import { api } from "@/lib/api";


interface Task {
  id: string;
  title: string;
  status: string;
  story_points: number;
  priority: number;
}

const COLUMNS = [
  { id: "todo", label: "To do" },
  { id: "in_progress", label: "Doing" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" },
];

export default function MobileKanban() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["tasks", id],
    queryFn: async () => (await api.get<Task[]>(`/api/projects/${id}/tasks`)).data,
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
    <ScrollView horizontal contentContainerClassName="p-3">
      {COLUMNS.map((col) => {
        const items = (data ?? []).filter((t) => t.status === col.id);
        return (
          <View
            key={col.id}
            className="w-64 bg-slate-100 rounded-md p-2 mr-3"
          >
            <Text className="font-semibold text-slate-700 mb-2">
              {col.label} <Text className="text-xs text-slate-500">({items.length})</Text>
            </Text>
            {items.map((t) => (
              <View key={t.id} className="bg-white rounded p-2 mb-1.5 border border-slate-200">
                <Text className="text-sm text-slate-800">{t.title}</Text>
                <Text className="text-[10px] text-slate-500 mt-1">
                  {t.story_points} sp · pri {t.priority}
                </Text>
              </View>
            ))}
            {items.length === 0 && (
              <Text className="text-[10px] text-slate-400 italic">Trống</Text>
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}
