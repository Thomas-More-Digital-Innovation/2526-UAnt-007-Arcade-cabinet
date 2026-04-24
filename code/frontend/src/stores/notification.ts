import { defineStore } from 'pinia';
import { ref } from 'vue';

export type NotificationType = 'positive' | 'negative' | 'warning' | 'info';

export interface NotificationOptions {
  type?: NotificationType;
  message: string;
  timeout?: number;
}

export const useNotificationStore = defineStore('notification', () => {
  const isOpen = ref(false);
  const type = ref<NotificationType>('info');
  const message = ref('');

  function notify(options: NotificationOptions | string) {
    if (typeof options === 'string') {
      message.value = options;
      type.value = 'info';
    } else {
      message.value = options.message;
      type.value = options.type || 'info';
    }
    isOpen.value = true;
  }

  function close() {
    isOpen.value = false;
  }

  return {
    isOpen,
    type,
    message,
    notify,
    close
  };
});
