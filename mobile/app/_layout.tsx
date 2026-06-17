import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { AuthProvider } from "@/providers/AuthProvider";
import { PushTokenRegistrar } from "@/components/PushTokenRegistrar";


export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <PushTokenRegistrar />
          <StatusBar style="auto" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: "#0ea5e9" },
              headerTintColor: "#fff",
              contentStyle: { backgroundColor: "#f8fafc" },
            }}
          >
            <Stack.Screen name="(auth)/login" options={{ title: "Đăng nhập" }} />
            <Stack.Screen name="(auth)/register" options={{ title: "Đăng ký" }} />
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen
              name="projects/[id]/kanban"
              options={{ title: "Kanban" }}
            />
            <Stack.Screen
              name="projects/[id]/meeting"
              options={{ title: "Biên bản họp" }}
            />
          </Stack>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
