# Admin Dashboard Management System - Complete Guide

## Overview
You now have a fully functional admin management system with the following capabilities:

## Features Available

### 1. User Management
**URL:** `/manage/users/`
- View all users with their roles and status
- Create new users (automatically creates clinician/patient profiles)
- Edit existing users (username, email, name, role, password, status)
- Delete users (cannot delete yourself for safety)

### 2. Clinician Management
**URL:** `/manage/clinicians/`
- View all clinician profiles
- See details: username, email, full name
- View count of assigned patients
- Edit the underlying user account

### 3. Patient Management
**URL:** `/manage/patients/`
- View all patient profiles
- See details: username, email, full name
- View assigned clinicians
- View pressure frame count
- Edit the underlying user account

### 4. Assignments Management
**URL:** `/assignments/`
- Manage patient-clinician assignments
- Create new assignments
- Remove assignments
- View all current assignments

### 5. Pressure Data Management
**URL:** `/manage/pressure-data/`
- Browser all sensor pressure frames
- Filter by patient
- View detailed frame information with heatmap visualization
- Delete individual frames
- See peak pressure, contact area, and high-pressure flags

### 6. Comments Management
**URL:** `/manage/comments/`
- View all user comments
- See comment details and clinician replies
- Delete comments as needed

## How to Access

1. **Login as Admin:**
   - Go to `/login/`
   - Use admin credentials

2. **Go to Admin Dashboard:**
   - After login, click "Admin" in the nav or go to `/admin-dashboard/`

3. **Access Management Functions:**
   - Click the appropriate card on the dashboard
   - Each management page has a table with action buttons

## User Roles

- **Admin:** Can access all management features
- **Clinician:** Can only view assigned patients
- **Patient:** Can only view their own pressure data

## Security Features

- ✓ All management views require admin role
- ✓ Cannot delete your own user account
- ✓ Proper HTML escaping for all data
- ✓ CSRF protection on all forms
- ✓ Confirmation dialogs for destructive actions

## Database Operations

### Creating Users
- When you create a user with "Clinician" role, a ClinicianProfile is auto-created
- When you create a user with "Patient" role, a PatientProfile is auto-created
- Admin users don't get profiles

### Pressure Frame Data
- Each frame includes: timestamp, 32x32 pressure matrix, statistics
- Heatmap visualization shows pressure distribution
- High-pressure flags can be monitored

### Comments
- Users can leave comments on pressure frames
- Clinicians can reply to comments
- All comments can be managed from the admin panel

## URL Structure

```
/manage/ - All management features prefix
  /users/                           - User list
  /users/create/                    - Create user
  /users/<id>/edit/                 - Edit user
  /users/<id>/delete/               - Delete user
  /clinicians/                      - Clinician list
  /patients/                        - Patient list
  /pressure-data/                   - Pressure data list
  /pressure-data/<id>/              - Pressure frame detail
  /pressure-data/<id>/delete/       - Delete pressure frame
  /comments/                        - Comment list
  /comments/<id>/delete/            - Delete comment
```

## Tips

1. Use the patient filter on pressure data to find specific patient's data
2. Click on frame ID in comments to view that pressure frame
3. Always confirm before deleting important data
4. Edit users to change roles or deactivate accounts
5. Password reset is available when editing user accounts

---
**Implementation Date:** March 17, 2026
**Status:** Fully Functional ✓
