<template>
  <q-dialog v-model="store.isOpen">
    <q-card class="notification-card">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6 flex items-center gap-2">
          <q-icon :name="icon" size="sm" />
          <span class="text-capitalize">{{ store.type }}</span>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>

      <q-card-section class="q-pt-md text-body1">
        {{ store.message }}
      </q-card-section>

      <q-card-actions align="right" class="q-pb-md q-pr-md">
        <q-btn unelevated label="Dismiss" color="primary" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useNotificationStore } from '../stores/notification';

const store = useNotificationStore();

const icon = computed(() => {
  switch (store.type) {
    case 'positive': return 'check_circle';
    case 'negative': return 'error';
    case 'warning': return 'warning';
    case 'info': return 'info';
    default: return 'info';
  }
});
</script>

<style scoped>
.notification-card {
  min-width: 350px;
  max-width: 500px;
  transition: all 0.3s ease;
}


.text-capitalize {
  text-transform: capitalize;
}
</style>
