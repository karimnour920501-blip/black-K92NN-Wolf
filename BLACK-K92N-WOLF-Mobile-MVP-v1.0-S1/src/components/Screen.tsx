import React from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { tokens } from '../design/tokens';
export function Screen({title,subtitle,children}:{title:string;subtitle?:string;children:React.ReactNode}) {
  return <SafeAreaView style={{flex:1,backgroundColor:tokens.colors.background}} edges={['top']}>
    <ScrollView contentContainerStyle={{padding:20,paddingBottom:44}}>
      <Text accessibilityRole="header" style={{color:tokens.colors.gold,fontWeight:'800',marginBottom:26}}>BLACK-K92N-WOLF</Text>
      <Text accessibilityRole="header" style={{color:tokens.colors.text,fontSize:tokens.typography.title,fontWeight:'700'}}>{title}</Text>
      {subtitle ? <Text style={{color:tokens.colors.muted,marginTop:10}}>{subtitle}</Text> : null}
      <View style={{marginTop:24,gap:12}}>{children}</View>
    </ScrollView>
  </SafeAreaView>;
}
