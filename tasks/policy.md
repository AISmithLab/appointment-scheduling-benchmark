# Synthetic Clinic Scheduling Policy

These rules apply only inside this benchmark's synthetic clinic.

1. **In-network care:** A provider is in network only when the patient's insurance appears in the provider's `accepted_insurance` list.
2. **Early afternoon:** Interpret “early afternoon” as 1:00 PM inclusive through 3:00 PM exclusive.
3. **Referral requirement:** Cardiology and neurology appointments require an active, unexpired referral for that specialty. An expired or missing referral means the agent must not reschedule and should record a decline.
4. **Pediatric eligibility:** Patients under age 18 may be scheduled only with a provider whose `pediatric_eligible` field is true.
5. **Authorized requester:** Only the patient or an explicitly authorized proxy may change an adult patient's appointment. A roommate, friend, or other unlisted person is not authorized.
6. **Conditional no-op:** When the requester says to leave the appointment unchanged unless a condition is satisfied, failure to satisfy the condition requires a true no-op: do not reschedule and do not record a decline.
7. **Changing availability:** A slot may become unavailable between search and booking. After such a tool error, search again and use the next valid option rather than claiming success.
8. **No double-booking:** Do not place the same patient into two appointments with the same start time.
