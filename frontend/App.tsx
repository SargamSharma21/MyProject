import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  ScrollView, ActivityIndicator, Alert, Modal, Vibration, Image as RNImage, Dimensions
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import * as ImagePicker from 'expo-image-picker';
import * as Notifications from 'expo-notifications';
import * as FileSystem from 'expo-file-system/legacy';
import { FileSystemUploadType } from 'expo-file-system/legacy';
import Constants from 'expo-constants';

const hostUri = Constants.expoConfig?.hostUri;
const detectedIp = hostUri ? hostUri.split(':')[0] : '192.168.60.108';
const BACKEND_URL = `http://${detectedIp}:8000`;

interface PrescriptionHistoryItem {
  id: string;
  doctor_name: string;
  clinic_name: string;
  prescription_date: string;
  image_url: string;
  medicines: any[];
  created_at: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'scan' | 'vault' | 'search'>('scan');
  const [loading, setLoading] = useState(false);

  // Scan State
  const [extractedMedicines, setExtractedMedicines] = useState<any[]>([]);
  const [doctorInfo, setDoctorInfo] = useState<{ doctor?: string; clinic?: string; date?: string }>({});

  // Vault State
  const [historyRecords, setHistoryRecords] = useState<PrescriptionHistoryItem[]>([]);
  const [selectedImageModal, setSelectedImageModal] = useState<string | null>(null);

  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);

  // Alarm State
  const [alarmActive, setAlarmActive] = useState(false);
  const [ringingMed, setRingingMed] = useState<{ name: string; dosage?: string; instructions?: string } | null>(null);

  useEffect(() => {
    (async () => {
      await Notifications.requestPermissionsAsync();
    })();

    const notifSub = Notifications.addNotificationReceivedListener(notification => {
      const data = notification.request.content.data;
      if (data?.isAlarm) triggerAlarm(data);
    });

    const respSub = Notifications.addNotificationResponseReceivedListener(response => {
      const data = response.notification.request.content.data;
      if (data?.isAlarm) triggerAlarm(data);
    });

    return () => {
      notifSub.remove();
      respSub.remove();
      Vibration.cancel();
    };
  }, []);

  const triggerAlarm = (medData: any) => {
    setRingingMed(medData);
    setAlarmActive(true);
    Vibration.vibrate([1000, 500], true);
  };

  const stopAlarm = () => {
    Vibration.cancel();
    setAlarmActive(false);
    setRingingMed(null);
  };

  const fetchVaultHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/prescriptions/history`);
      const data = await res.json();
      setHistoryRecords(data);
    } catch {
      Alert.alert("Error", "Unable to load vault history.");
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab: 'scan' | 'vault' | 'search') => {
    setActiveTab(tab);
    if (tab === 'vault') {
      fetchVaultHistory();
    }
  };

  const handleUploadAndScan = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) return;

      const pickerResult = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        quality: 0.8,
      });

      if (pickerResult.canceled || !pickerResult.assets?.length) return;

      setLoading(true);
      const targetUri = pickerResult.assets[0].uri;

      const uploadResponse = await FileSystem.uploadAsync(
        `${BACKEND_URL}/api/v1/prescriptions/upload-and-scan`,
        targetUri,
        {
          fieldName: 'file',
          httpMethod: 'POST',
          uploadType: FileSystemUploadType.MULTIPART,
          mimeType: 'image/jpeg',
        }
      );

      if (uploadResponse.status >= 200 && uploadResponse.status < 300) {
        const data = JSON.parse(uploadResponse.body);
        setExtractedMedicines(data.extracted_data.medicines || []);
        setDoctorInfo({
          doctor: data.extracted_data.doctor_name,
          clinic: data.extracted_data.clinic_name,
          date: data.extracted_data.prescription_date,
        });
        Alert.alert("Success", "Prescription archived to Vault!");
      }
    } catch (err: any) {
      Alert.alert("Error", err.message || "Failed to scan.");
    } finally {
      setLoading(false);
    }
  };

  const scheduleAlarm = async (med: any) => {
    try {
      await Notifications.scheduleNotificationAsync({
        content: {
          title: `Medicine Alarm: ${med.name}`,
          body: `Take ${med.dosage || ''}. Timing: ${med.timing === 'AC' ? 'Before Food' : 'After Food'}`,
          sound: true,
          data: {
            isAlarm: true,
            name: med.name,
            dosage: med.dosage,
            instructions: med.timing === 'AC' ? 'Before Food' : 'After Food',
          },
        },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
          seconds: 5,
          repeats: false,
        },
      });
      Alert.alert("Alarm Set", `Test alarm set for ${med.name}! Rings in 5 seconds.`);
    } catch (err: any) {
      Alert.alert("Error", err.message);
    }
  };

  const handleSearch = async () => {
    if (searchQuery.trim().length < 2) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/medicines/search?q=${encodeURIComponent(searchQuery)}`);
      const data = await res.json();
      setSearchResults(data);
    } catch {
      Alert.alert("Error", "Failed to connect to safety database.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        {/* Top Tab Bar */}
        <View style={styles.tabBar}>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'scan' && styles.activeTab]}
            onPress={() => handleTabChange('scan')}
          >
            <Text style={[styles.tabText, activeTab === 'scan' && styles.activeTabText]}>Scan</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'vault' && styles.activeTab]}
            onPress={() => handleTabChange('vault')}
          >
            <Text style={[styles.tabText, activeTab === 'vault' && styles.activeTabText]}>Vault</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, activeTab === 'search' && styles.activeTab]}
            onPress={() => handleTabChange('search')}
          >
            <Text style={[styles.tabText, activeTab === 'search' && styles.activeTabText]}>Drug Safety</Text>
          </TouchableOpacity>
        </View>

        {/* Tab 1: Scan Screen */}
        {activeTab === 'scan' && (
          <ScrollView contentContainerStyle={styles.scrollContent}>
            <Text style={styles.title}>Prescription Scanner</Text>
            <Text style={styles.disclaimer}>Verify all details with your doctor's slip before taking medication.</Text>

            <TouchableOpacity style={styles.primaryBtn} onPress={handleUploadAndScan} disabled={loading}>
              <Text style={styles.btnText}>{loading ? "Extracting & Archiving..." : "Upload Prescription Slip"}</Text>
            </TouchableOpacity>

            {loading && <ActivityIndicator size="large" color="#2563EB" style={{ marginVertical: 20 }} />}

            {doctorInfo.doctor && (
              <View style={styles.doctorCard}>
                <Text style={styles.doctorName}>{doctorInfo.doctor}</Text>
                <Text style={styles.doctorSub}>{doctorInfo.clinic || 'Medical Clinic'} • {doctorInfo.date || 'Recent'}</Text>
              </View>
            )}

            {extractedMedicines.map((med, idx) => (
              <View key={idx} style={styles.card}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.medName}>{med.name} {med.dosage ? `(${med.dosage})` : ''}</Text>
                  <Text style={styles.medDetails}>Form: {med.form || 'Tablet'} • {med.frequency}</Text>
                  <Text style={styles.medDetails}>Timing: {med.timing === 'AC' ? 'Before Food' : 'After Food'}</Text>
                </View>
                <TouchableOpacity style={styles.alarmBtn} onPress={() => scheduleAlarm(med)}>
                  <Text style={styles.alarmBtnText}>Alarm</Text>
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>
        )}

        {/* Tab 2: Vault Screen */}
        {activeTab === 'vault' && (
          <ScrollView contentContainerStyle={styles.scrollContent}>
            <Text style={styles.title}>Prescription Vault</Text>
            <Text style={styles.subtitle}>All archived doctor slips and previous medications.</Text>

            {loading && <ActivityIndicator size="large" color="#2563EB" style={{ marginVertical: 20 }} />}

            {historyRecords.length === 0 && !loading && (
              <Text style={{ color: '#94A3B8', marginTop: 20 }}>No prescriptions archived yet. Scan one to get started!</Text>
            )}

            {historyRecords.map((item) => (
              <View key={item.id} style={styles.vaultCard}>
                <View style={styles.vaultHeader}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.vaultDocName}>{item.doctor_name}</Text>
                    <Text style={styles.vaultSub}>{item.clinic_name} • {item.prescription_date}</Text>
                    <Text style={styles.vaultDate}>Archived: {item.created_at}</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.viewSlipBtn}
                    onPress={() => setSelectedImageModal(`${BACKEND_URL}${item.image_url}`)}
                  >
                    <Text style={styles.viewSlipText}>View Slip</Text>
                  </TouchableOpacity>
                </View>

                <View style={styles.vaultMedSection}>
                  <Text style={styles.vaultMedHeading}>Prescribed Medicines ({item.medicines.length}):</Text>
                  {item.medicines.map((m, mIdx) => (
                    <Text key={mIdx} style={styles.vaultMedItem}>
                      • <Text style={{ fontWeight: '700' }}>{m.name}</Text> ({m.dosage || 'Standard'}) - {m.frequency}
                    </Text>
                  ))}
                </View>
              </View>
            ))}
          </ScrollView>
        )}

        {/* Tab 3: Drug Safety Screen */}
        {activeTab === 'search' && (
          <ScrollView contentContainerStyle={styles.scrollContent}>
            <Text style={styles.title}>Drug Safety Knowledge</Text>
            <View style={styles.searchRow}>
              <TextInput
                style={styles.searchInput}
                placeholder="Search drug e.g. Atorvastatin, Dolo..."
                value={searchQuery}
                onChangeText={setSearchQuery}
              />
              <TouchableOpacity style={styles.searchBtn} onPress={handleSearch}>
                <Text style={styles.btnText}>Search</Text>
              </TouchableOpacity>
            </View>

            {searchResults.map((item, idx) => (
              <View key={idx} style={styles.insightCard}>
                <Text style={styles.brandTitle}>{item.brand_name}</Text>
                <Text style={styles.genericSub}>{item.generic_name}</Text>
                <Text style={styles.sectionHeader}>Primary Uses:</Text>
                <Text style={styles.bodyText}>{item.uses}</Text>
                <Text style={styles.sectionHeader}>Side Effects:</Text>
                <Text style={styles.bodyText}>{item.side_effects}</Text>
                <Text style={[styles.sectionHeader, { color: '#DC2626' }]}>Contraindications:</Text>
                <Text style={styles.bodyText}>{item.contraindications}</Text>
                <Text style={styles.sectionHeader}>Food Interactions:</Text>
                <Text style={styles.bodyText}>{item.food_interactions}</Text>
              </View>
            ))}
          </ScrollView>
        )}

        {/* Full Screen Doctor Slip Modal */}
        <Modal visible={!!selectedImageModal} transparent={false} animationType="fade">
          <SafeAreaView style={styles.modalImageViewer}>
            <TouchableOpacity style={styles.closeModalBtn} onPress={() => setSelectedImageModal(null)}>
              <Text style={styles.closeModalText}>✕ Close</Text>
            </TouchableOpacity>
            {selectedImageModal && (
              <RNImage
                source={{ uri: selectedImageModal }}
                style={styles.fullScreenImage}
                resizeMode="contain"
              />
            )}
          </SafeAreaView>
        </Modal>

        {/* Alarm Full-Screen Modal */}
        <Modal visible={alarmActive} animationType="slide" transparent={false}>
          <SafeAreaView style={styles.alarmScreenContainer}>
            <View style={styles.alarmContent}>
              <Text style={styles.alarmHeader}>Medication Alarm</Text>
              <Text style={styles.alarmMedName}>{ringingMed?.name}</Text>
              <Text style={styles.alarmDosage}>{ringingMed?.dosage || 'Standard Dosage'}</Text>
              <Text style={styles.alarmInstructions}>{ringingMed?.instructions}</Text>
              <View style={styles.alarmBtnGroup}>
                <TouchableOpacity style={styles.tookItBtn} onPress={() => { stopAlarm(); Alert.alert("Confirmed", "Dose logged."); }}>
                  <Text style={styles.tookItBtnText}>I Took It</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.snoozeBtn} onPress={() => { stopAlarm(); Alert.alert("Snoozed", "Reminder delayed 5 mins."); }}>
                  <Text style={styles.snoozeBtnText}>Snooze (5 min)</Text>
                </TouchableOpacity>
              </View>
            </View>
          </SafeAreaView>
        </Modal>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  scrollContent: { padding: 20, paddingBottom: 60 },
  tabBar: { flexDirection: 'row', backgroundColor: '#E2E8F0', margin: 16, borderRadius: 8, padding: 4 },
  tabButton: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: 6 },
  activeTab: { backgroundColor: '#FFFFFF' },
  tabText: { fontWeight: '600', color: '#64748B', fontSize: 13 },
  activeTabText: { color: '#0F172A' },
  title: { fontSize: 24, fontWeight: '700', color: '#0F172A', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#64748B', marginBottom: 16 },
  disclaimer: { fontSize: 12, color: '#DC2626', marginBottom: 16 },
  primaryBtn: { backgroundColor: '#2563EB', padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  btnText: { color: '#FFFFFF', fontWeight: '600', fontSize: 15 },
  doctorCard: { backgroundColor: '#EFF6FF', padding: 14, borderRadius: 8, marginBottom: 16, borderWidth: 1, borderColor: '#BFDBFE' },
  doctorName: { fontSize: 16, fontWeight: '700', color: '#1D4ED8' },
  doctorSub: { fontSize: 13, color: '#3B82F6', marginTop: 2 },
  card: { backgroundColor: '#FFFFFF', padding: 16, borderRadius: 8, marginBottom: 12, flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: '#E2E8F0' },
  medName: { fontSize: 16, fontWeight: '700', color: '#1E293B' },
  medDetails: { fontSize: 13, color: '#64748B', marginTop: 2 },
  alarmBtn: { backgroundColor: '#10B981', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 6 },
  alarmBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 12 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  searchInput: { flex: 1, backgroundColor: '#FFFFFF', padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1' },
  searchBtn: { backgroundColor: '#2563EB', paddingHorizontal: 18, justifyContent: 'center', borderRadius: 8 },
  insightCard: { backgroundColor: '#FFFFFF', padding: 16, borderRadius: 8, marginBottom: 14, borderWidth: 1, borderColor: '#E2E8F0' },
  brandTitle: { fontSize: 18, fontWeight: '700', color: '#0F172A' },
  genericSub: { fontSize: 14, fontStyle: 'italic', color: '#64748B', marginBottom: 8 },
  sectionHeader: { fontSize: 13, fontWeight: '700', color: '#334155', marginTop: 10 },
  bodyText: { fontSize: 13, color: '#475569', marginTop: 2, lineHeight: 18 },
  vaultCard: { backgroundColor: '#FFFFFF', padding: 16, borderRadius: 10, marginBottom: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  vaultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', borderBottomWidth: 1, borderBottomColor: '#F1F5F9', paddingBottom: 10 },
  vaultDocName: { fontSize: 16, fontWeight: '700', color: '#1E293B' },
  vaultSub: { fontSize: 13, color: '#475569', marginTop: 2 },
  vaultDate: { fontSize: 11, color: '#94A3B8', marginTop: 4 },
  viewSlipBtn: { backgroundColor: '#EFF6FF', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6, borderWidth: 1, borderColor: '#BFDBFE' },
  viewSlipText: { color: '#2563EB', fontSize: 12, fontWeight: '700' },
  vaultMedSection: { marginTop: 12 },
  vaultMedHeading: { fontSize: 13, fontWeight: '700', color: '#334155', marginBottom: 6 },
  vaultMedItem: { fontSize: 13, color: '#475569', marginBottom: 4 },
  modalImageViewer: { flex: 1, backgroundColor: '#000000', justifyContent: 'center', alignItems: 'center' },
  closeModalBtn: { position: 'absolute', top: 50, right: 20, zIndex: 10, backgroundColor: 'rgba(255,255,255,0.2)', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20 },
  closeModalText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
  fullScreenImage: { width: Dimensions.get('window').width, height: Dimensions.get('window').height * 0.8 },
  alarmScreenContainer: { flex: 1, backgroundColor: '#0F172A', justifyContent: 'center', alignItems: 'center' },
  alarmContent: { alignItems: 'center', paddingHorizontal: 30, width: '100%' },
  alarmHeader: { color: '#EF4444', fontSize: 20, fontWeight: '800', letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 20 },
  alarmMedName: { color: '#FFFFFF', fontSize: 32, fontWeight: '800', textAlign: 'center' },
  alarmDosage: { color: '#94A3B8', fontSize: 20, marginTop: 8 },
  alarmInstructions: { color: '#38BDF8', fontSize: 16, marginTop: 12, fontWeight: '600' },
  alarmBtnGroup: { marginTop: 60, width: '100%', gap: 16 },
  tookItBtn: { backgroundColor: '#10B981', paddingVertical: 18, borderRadius: 12, alignItems: 'center' },
  tookItBtnText: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
  snoozeBtn: { backgroundColor: '#334155', paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
  snoozeBtnText: { color: '#E2E8F0', fontSize: 15, fontWeight: '600' },
});