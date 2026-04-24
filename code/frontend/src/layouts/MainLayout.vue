<template>
  <q-layout view="hHh lpR fFf">

    <q-header class="bg-primary text-white" height-hint="98">
      <q-toolbar>
        <q-toolbar-title>
          UAntwerpen Arcade Cabinet
        </q-toolbar-title>
      </q-toolbar>

      <q-tabs align="left">
        <q-route-tab to="/" label="Games" />
        <!-- <q-route-tab to="/status" label="Current Status" /> -->
      </q-tabs>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>

    <notification-dialog />
  </q-layout>
</template>

<script setup lang="ts">
import NotificationDialog from 'src/components/NotificationDialog.vue';
</script>
