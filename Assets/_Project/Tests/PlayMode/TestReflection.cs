using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace QuickDraw.Tests.PlayMode
{
    internal static class TestReflection
    {
        internal static Type RequireType(string qualifiedName)
        {
            Type type = Type.GetType(qualifiedName);
            Assert.That(type, Is.Not.Null, $"Could not find {qualifiedName}.");
            return type;
        }

        internal static GameObject RequireObject(string objectName)
        {
            GameObject result = GameObject.Find(objectName);
            Assert.That(result, Is.Not.Null, $"Missing {objectName}.");
            return result;
        }

        internal static T ReadPrivateField<T>(object instance, string fieldName)
        {
            FieldInfo field = instance.GetType().GetField(
                fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        internal static T ReadProperty<T>(object instance, string propertyName)
        {
            PropertyInfo property = instance.GetType().GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(instance);
        }

        internal static void Invoke(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }

        internal static T InvokeResult<T>(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            return (T)method.Invoke(instance, arguments);
        }

        internal static void InvokePrivate(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }
    }
}
