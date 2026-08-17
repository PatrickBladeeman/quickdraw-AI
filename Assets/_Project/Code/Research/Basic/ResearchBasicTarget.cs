using System;
using UnityEngine;

namespace QuickDraw.Research.Basic
{
    [DisallowMultipleComponent]
    public sealed class ResearchBasicTarget : MonoBehaviour
    {
        private Vector3 _origin;
        private bool _initialized;

        public int Slot { get; private set; }

        public void SetSlot(int slot)
        {
            if (slot < ResearchBasicContract.MinimumSlot ||
                slot > ResearchBasicContract.MaximumSlot)
            {
                throw new ArgumentOutOfRangeException(nameof(slot));
            }

            EnsureInitialized();
            Slot = slot;
            transform.position = _origin +
                Vector3.right * (slot * ResearchBasicContract.SlotSpacing);
        }

        private void EnsureInitialized()
        {
            if (_initialized)
            {
                return;
            }

            _origin = transform.position;
            _initialized = true;
        }
    }
}
