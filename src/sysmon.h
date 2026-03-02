#pragma once

//
// AirBridge.S3 — System monitor helpers
// CPU utilization (from FreeRTOS idle task) and free heap memory
//

#include <Arduino.h>
#include <esp_system.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <string.h>

// Returns CPU usage as a percentage (0-100).
// Uses uxTaskGetSystemState() to sum idle task runtime across both cores.
// Call periodically (e.g. every 2s from display refresh).
inline int sysmon_cpu_percent() {
    static uint32_t prev_idle_total = 0;
    static uint32_t prev_run_total = 0;

    // Get state of all tasks
    TaskStatus_t tasks[32];
    uint32_t total_runtime = 0;
    UBaseType_t count = uxTaskGetSystemState(tasks, 32, &total_runtime);

    // Sum idle task runtime (both cores: "IDLE0" and "IDLE1", or just "IDLE")
    uint32_t idle_total = 0;
    for (UBaseType_t i = 0; i < count; i++) {
        if (strncmp(tasks[i].pcTaskName, "IDLE", 4) == 0) {
            idle_total += tasks[i].ulRunTimeCounter;
        }
    }

    uint32_t delta_run  = total_runtime - prev_run_total;
    uint32_t delta_idle = idle_total - prev_idle_total;
    prev_idle_total = idle_total;
    prev_run_total  = total_runtime;

    if (delta_run == 0) return 0;

    // delta_run already accounts for both cores' time
    int idle_pct = (int)((delta_idle * 100) / delta_run);
    int cpu_pct = 100 - idle_pct;
    if (cpu_pct < 0) cpu_pct = 0;
    if (cpu_pct > 100) cpu_pct = 100;
    return cpu_pct;
}

// Returns free heap memory in kilobytes
inline int sysmon_free_heap_kb() {
    return (int)(esp_get_free_heap_size() / 1024);
}
